# -*- coding: utf-8 -*-
"""Does the claim gate fire exactly when it should, and never otherwise?"""
import io, json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
ROOT = r"C:\Claude-Code"
TEST_FOLDER = os.path.join(ROOT, "_gatetest")
PY = sys.executable
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def transcript(path, reply, tools, ts="2026-10-19T10:00:00.000Z"):
    rows = [json.dumps({"type": "user", "origin": {"kind": "human"},
                        "timestamp": ts,
                        "message": {"role": "user", "content": "do the thing"}})]
    content = []
    for name, inp in tools:
        content.append({"type": "tool_use", "name": name, "input": inp})
    content.append({"type": "text", "text": reply})
    rows.append(json.dumps({"type": "assistant", "timestamp": ts,
                            "message": {"role": "assistant", "content": content}}))
    io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(rows) + "\n")


def run(tpath, sid="s1", cwd=TEST_FOLDER):
    p = subprocess.run(
        [PY, "-X", "utf8", os.path.join(HERE, "hook_claim_gate.py")],
        input=json.dumps({"session_id": sid, "transcript_path": tpath,
                          "cwd": cwd, "hook_event_name": "Stop"}),
        capture_output=True, text=True)
    blocked = False
    reason = ""
    if p.stdout.strip():
        try:
            d = json.loads(p.stdout)
            blocked = d.get("decision") == "block"
            reason = d.get("reason", "")
        except Exception:
            pass
    return p.returncode, blocked, reason, p.stderr


# a non-UI change, so these cases exercise the generic evidence tier.
# UI files go through the stricter visual tier, tested separately below.
WRITE = ("Write", {"file_path": r"C:\Claude-Code\_gatetest\build.py",
                   "content": "x"})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    os.makedirs(TEST_FOLDER, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="gate_")
    t = os.path.join(tmp, "t.jsonl")
    state = os.path.join(SYS, "gate-state.json")
    saved = io.open(state, encoding="utf-8").read() if os.path.isfile(state) else None

    def reset():
        try:
            os.remove(state)
        except Exception:
            pass

    # 1 - the case it exists for
    reset(); transcript(t, "Done. The services page is live.", [WRITE])
    rc, blocked, reason, err = run(t)
    ok("claim + change + no check -> BLOCKS", blocked, err.strip()[:70])
    ok("block reason names the claim", "done" in reason.lower())
    ok("block reason says what to do", "screenshot" in reason.lower())

    # 2 - evidence in various forms
    for label, tool in [
        ("Read", ("Read", {"file_path": "x"})),
        ("curl", ("Bash", {"command": "curl -s -o /dev/null -w '%{http_code}' https://x"})),
        ("build", ("Bash", {"command": "npm run build"})),
        ("rqa", ("Bash", {"command": "node rqa.js https://x --out q"})),
        ("screenshot", ("mcp__Claude_Browser__computer", {"action": "screenshot"})),
        ("git diff", ("Bash", {"command": "git diff --stat"})),
        # this system's own suites count as checks; they are how it is verified
        ("gatetest", ("Bash", {"command": "python gatetest.py"})),
        ("install --status", ("Bash", {"command": "python install.py --status"})),
    ]:
        reset(); transcript(t, "Fixed. It works now.", [WRITE, tool])
        rc, blocked, _r, _e = run(t)
        ok("claim + %s -> allowed" % label, not blocked)

    # 3 - honest replies are never blocked
    reset()
    transcript(t, "I changed it, but I could not verify it from here yet.", [WRITE])
    rc, blocked, _r, _e = run(t)
    ok("hedged reply -> allowed", not blocked)

    reset()
    transcript(t, "Done. I have not tested the form yet, that needs your login.",
               [WRITE])
    rc, blocked, _r, _e = run(t)
    ok("claim + explicit 'not tested' -> allowed", not blocked)

    # 4 - nothing was changed, so nothing to verify
    reset(); transcript(t, "Done, that is all correct.", [])
    rc, blocked, _r, _e = run(t)
    ok("no change made -> allowed", not blocked)

    # 5 - no claim at all
    reset(); transcript(t, "Here is what I found in the config.", [WRITE])
    rc, blocked, _r, _e = run(t)
    ok("no claim -> allowed", not blocked)

    # 6 - loop guard
    reset(); transcript(t, "Done. Deployed.", [WRITE])
    _rc, b1, _r, _e = run(t)
    _rc, b2, _r, _e = run(t)
    ok("blocks once, then lets the same turn through", b1 and not b2,
       "first=%s second=%s" % (b1, b2))

    # 7 - outside the workspace
    reset(); transcript(t, "Done.", [WRITE])
    rc, blocked, _r, _e = run(t, cwd=os.environ.get("TEMP", r"C:\Temp"))
    ok("cwd outside the workspace -> ignored", not blocked)

    # 8 - the off switch
    cfg = os.path.join(SYS, "gate.json")
    io.open(cfg, "w", encoding="utf-8").write('{"enabled": false}')
    reset(); transcript(t, "Done. Live.", [WRITE])
    rc, blocked, _r, _e = run(t)
    ok("gate off -> allowed", not blocked)
    io.open(cfg, "w", encoding="utf-8").write('{"enabled": true}')

    # 9 - Hinglish claim
    reset(); transcript(t, "Ho gaya, page live hai ab.", [WRITE])
    rc, blocked, _r, _e = run(t)
    ok("Hinglish claim -> blocks", blocked)

    # --- the visual tier: eyes, not code ---
    CSS = ("Write", {"file_path": r"C:\Claude-Code\_gatetest\hero.tsx",
                     "content": "x"})
    SHOT = ("mcp__Claude_Browser__computer", {"action": "screenshot"})
    RQA = ("Bash", {"command": 'node rqa.js https://x --out q'})

    reset(); transcript(t, "Done, the hero looks right now.", [CSS,
                        ("Bash", {"command": "git diff --stat"})])
    _rc, blocked, reason, _e = run(t)
    ok("UI change + non-visual check -> BLOCKS", blocked)
    ok("visual block asks for screenshots", "390px" in reason)
    ok("visual block says code review is not looking",
       "not looking" in reason.lower())

    reset(); transcript(t, "Done, the hero looks right now.", [CSS, SHOT])
    _rc, blocked, _r, _e = run(t)
    ok("UI change + screenshot -> allowed", not blocked)

    reset(); transcript(t, "Fixed the layout.", [CSS, RQA])
    _rc, blocked, _r, _e = run(t)
    ok("UI change + rqa.js -> allowed", not blocked)

    reset(); transcript(t, "Done. The page is live.",
                        [("Write", {"file_path": "notes.md", "content": "x"}),
                         ("Bash", {"command": "curl -s https://x"})])
    _rc, blocked, _r, _e = run(t)
    ok("visual word in claim + only curl -> BLOCKS", blocked)

    reset(); transcript(t, "Done, the migration script now handles 44 rows.",
                        [("Write", {"file_path": "migrate.py", "content": "x"}),
                         ("Bash", {"command": "pytest -q"})])
    _rc, blocked, _r, _e = run(t)
    ok("non-visual claim + tests -> allowed", not blocked)

    reset(); transcript(t, "Done, the hero looks right now.",
                        [CSS, ("Read", {"file_path": "qa/shot-390.png"})])
    _rc, blocked, _r, _e = run(t)
    ok("UI change + reading the screenshot file -> allowed", not blocked)

    reset(); transcript(t, "Done, the hero looks right now.",
                        [CSS, ("Read", {"file_path": "qa/notes.md"})])
    _rc, blocked, _r, _e = run(t)
    ok("UI change + reading a text file -> still BLOCKS", blocked)

    # a claim and a visual word in unrelated sentences is not a visual claim
    reset(); transcript(t, "The tests all pass and the leak check is done.\n"
                           "Separately: pushing is your button to press.",
                        [("Write", {"file_path": "build.py", "content": "x"}),
                         ("Bash", {"command": "pytest -q"})])
    _rc, blocked, _r, _e = run(t)
    ok("claim and visual word in different sentences -> allowed", not blocked)

    reset(); transcript(t, "Checked the config. Done, the button looks right.",
                        [("Write", {"file_path": "build.py", "content": "x"}),
                         ("Bash", {"command": "pytest -q"})])
    _rc, blocked, _r, _e = run(t)
    ok("claim and visual word in the SAME sentence -> BLOCKS", blocked)

    # "section" means a section of a document at least as often as a section
    # of a page. Every skill and brief this system writes is made of them, and
    # treating the bare word as visual demanded a screenshot of a Markdown file.
    reset(); transcript(t, "32 passing checks, and the older skill already "
                           "had a section saying the same thing.",
                        [("Write", {"file_path": "SKILL.md", "content": "x"}),
                         ("Bash", {"command": "pytest -q"})])
    _rc, blocked, _r, _e = run(t)
    ok("a document section in a claim -> allowed", not blocked)

    reset(); transcript(t, "Done, the hero section is cut off on mobile now.",
                        [("Write", {"file_path": "build.py", "content": "x"}),
                         ("Bash", {"command": "pytest -q"})])
    _rc, blocked, _r, _e = run(t)
    ok("a hero section in a claim -> still BLOCKS", blocked)

    reset(); transcript(t, "The section padding is fixed and matches now.",
                        [("Write", {"file_path": "notes.md", "content": "x"}),
                         ("Bash", {"command": "pytest -q"})])
    _rc, blocked, _r, _e = run(t)
    ok("a section's visual property in a claim -> still BLOCKS", blocked)


    # A .js is usually a page and sometimes a command-line tool. This system is
    # largely the second kind, and asking for a screenshot of a page that was
    # never written is how a gate gets switched off.
    node_js = os.path.join(TEST_FOLDER, "tool.js")
    io.open(node_js, "w", encoding="utf-8").write(
        'const fs = require("fs");\nmodule.exports = { go() { return 1; } };\n')
    browser_js = os.path.join(TEST_FOLDER, "widget.js")
    io.open(browser_js, "w", encoding="utf-8").write(
        'document.querySelector(".hero").classList.add("ready");\n')

    reset(); transcript(t, "Done, 30 checks pass.",
                        [("Write", {"file_path": node_js, "content": "x"}),
                         ("Bash", {"command": "npm test"})])
    _rc, blocked, _r, _e = run(t)
    ok("a Node command-line script is not a page -> allowed", not blocked)

    reset(); transcript(t, "Done, 30 checks pass.",
                        [("Write", {"file_path": browser_js, "content": "x"}),
                         ("Bash", {"command": "npm test"})])
    _rc, blocked, _r, _e = run(t)
    ok("a browser script with no Node markers -> still BLOCKS", blocked)

    reset(); transcript(t, "Done, the build passes.",
                        [("Write", {"file_path": os.path.join(TEST_FOLDER, "Hero.tsx"),
                                    "content": "x"}),
                         ("Bash", {"command": "npm run build"})])
    _rc, blocked, _r, _e = run(t)
    ok("a component file -> still BLOCKS", blocked)

    reset(); transcript(t, "Done, the build passes.",
                        [("Write", {"file_path": os.path.join(TEST_FOLDER, "site.css"),
                                    "content": "x"}),
                         ("Bash", {"command": "npm run build"})])
    _rc, blocked, _r, _e = run(t)
    ok("a stylesheet -> still BLOCKS", blocked)

    reset(); transcript(t, "Done, 30 checks pass.",
                        [("Write", {"file_path": os.path.join(TEST_FOLDER, "gone.js"),
                                    "content": "x"}),
                         ("Bash", {"command": "npm test"})])
    _rc, blocked, _r, _e = run(t)
    ok("a .js that cannot be read is treated as a page -> BLOCKS", blocked)


    # Only gatetest.py was named, so running ten of this system's own suites
    # and saying so was read as no evidence at all.
    for suite in ("python materialstest.py", "node designmdtest.js",
                  "node perftest.js"):
        reset(); transcript(t, "Done, every suite passes.",
                            [WRITE, ("Bash", {"command": suite})])
        _rc, blocked, _r, _e = run(t)
        ok("running %s counts as evidence" % suite.split()[-1], not blocked)

    reset(); transcript(t, "Done, every suite passes.",
                        [WRITE, ("Bash", {"command": "echo all good"})])
    _rc, blocked, _r, _e = run(t)
    ok("an echo is still not evidence", blocked)


    # Hinglish puts the subject first: "page theek ho gaya" claims something
    # about the page. Reversed it describes instead - "dugna ho gaya page" is
    # "the page that doubled", which is how a sentence explaining what a tool
    # measures reads, and it was blocking replies that claimed nothing.
    reset(); transcript(t, "Threshold bhaari page pakadta hai; dugna ho gaya "
                           "page sirf comparison pakadti hai.",
                        [WRITE, ("Bash", {"command": "npm test"})])
    _rc, blocked, _r, _e = run(t)
    ok("a claim word followed by the noun is a relative clause -> allowed",
       not blocked)

    reset(); transcript(t, "Page live ho gaya.",
                        [WRITE, ("Bash", {"command": "npm test"})])
    _rc, blocked, _r, _e = run(t)
    ok("subject first is still a claim -> BLOCKS", blocked)

    reset(); transcript(t, "Hero section ban gaya hai.",
                        [WRITE, ("Bash", {"command": "npm test"})])
    _rc, blocked, _r, _e = run(t)
    ok("a hero that was built -> still BLOCKS", blocked)

    reset(); transcript(t, "Fixed, the hero is cut off on mobile.",
                        [WRITE, ("Bash", {"command": "npm test"})])
    _rc, blocked, _r, _e = run(t)
    ok("an English claim with the visual word after a comma -> BLOCKS",
       blocked)

    # a claim word inside quoted speech is not the reply's own claim
    reset(); transcript(t, 'When you say "ho gaya", I will re-check the page.',
                        [CSS])
    _rc, blocked, _r, _e = run(t)
    ok("claim word only inside quotes -> allowed", not blocked)

    reset(); transcript(t, "Here is the plan:\n```\nstep 3: kar diya\n```\nAsk me.",
                        [CSS])
    _rc, blocked, _r, _e = run(t)
    ok("claim word only inside a code block -> allowed", not blocked)

    reset(); transcript(t, 'I said "something" earlier. Done, the hero is live.',
                        [CSS])
    _rc, blocked, _r, _e = run(t)
    ok("a real claim outside the quotes still BLOCKS", blocked)

    reset(); transcript(t, "Changed the hero, but I have not looked at it yet.",
                        [CSS])
    _rc, blocked, _r, _e = run(t)
    ok("UI change + honest 'not looked' -> allowed", not blocked)

    # 11 - the gate's first real miss, found 11 Nov by running it against the
    # recorded corpus instead of against invented examples. Romanised Hindi
    # agrees the auxiliary with the gender and number of the thing finished,
    # and only the masculine singular of each form was listed, so "ho gayi"
    # and "ho gaye" sailed through. The 51 cases above use "ho gaya" five
    # times and a feminine or plural form zero times, which is why they could
    # never fail on what the pattern was missing.
    #
    # So these are GENERATED from the families rather than typed out, and
    # pinned against the real corpus below. A fixture written from memory
    # tests the memory it came from.
    import collections
    import importlib.util
    import re as _re
    sys.path.insert(0, HERE)
    sys.path.insert(0, os.path.join(SYS, "context-system"))
    _spec = importlib.util.spec_from_file_location(
        "gate_under_test", os.path.join(HERE, "hook_claim_gate.py"))
    gate = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(gate)

    FAMILIES = {
        "ho ga": ["ya", "yi", "ye", "i"],
        "kar d": ["iya", "iye", "i"],
        "ban ga": ["ya", "yi", "ye", "i"],
        "lag ga": ["ya", "yi", "ye", "i"],
        "laga d": ["iya", "iye", "i"],
        "chal rah": ["a", "i", "e"],
    }
    for stem, endings in FAMILIES.items():
        missed = [stem + e for e in endings
                  if not gate.CLAIM.search(stem + e)]
        ok("every gender and number of '%s' counts as a claim" % (stem + endings[0]),
           not missed, ", ".join(missed) or "%d forms" % len(endings))

    notclaims = ["kar dijiye", "ho gayab", "ban gayi" + "sh", "chal rahat"]
    still = [w for w in notclaims if gate.CLAIM.search(w)]
    ok("a longer word that merely starts the same is not a claim",
       not still, ", ".join(still) or "4 non-words rejected")

    # end to end, one word apart, which is how the miss was proven
    for masc, variant in [
            ("Attribution theek ho gaya.", "Attribution theek ho gayi."),
            ("Dono kaam ho gaya, push kiya.", "Dono kaam ho gaye, push kiya."),
            ("Fix kar diya.", "Fix kar di."),
            ("Skill ban gaya.", "Skill ban gayi."),
            ("Image lag gaya.", "Image lag gayi.")]:
        reset(); transcript(t, masc, [WRITE])
        _rc, b_masc, _r, _e = run(t)
        reset(); transcript(t, variant, [WRITE])
        _rc, b_var, _r, _e = run(t)
        ok("'%s' blocks like '%s'" % (variant, masc), b_masc and b_var,
           "control %s, variant %s" % (b_masc, b_var))

    # 12 - "chal raha" is the one form that can mean the opposite of itself.
    # Widening it to the feminine and plural multiplied an exposure that was
    # already there, so the guard was added at the same time and has to be
    # pinned in BOTH directions or it is just a weaker gate.
    for reply, should_block, why in [
            ("Deploy chal raha hai, verification background mein.", False,
             "a job still running is not a claim"),
            ("Lighthouse ke 11 runs background me chal rahe hain.", False,
             "background work is not a claim"),
            ("Dono research agents chal rahe hain.", False,
             "agents still running is not a claim"),
            ("Site chal rahi hai, koi 500 nahi.", True,
             "a site that runs IS a claim"),
            ("Database aur app theek chal rahe hain.", True,
             "plural, and still a claim"),
            ("Super Charge abhi theek chal raha hai.", True,
             "'abhi' reads both ways and must not suppress a claim")]:
        reset(); transcript(t, reply, [WRITE])
        _rc, blocked, _r, _e = run(t)
        ok("%s -> %s" % (why, "BLOCKS" if should_block else "allowed"),
           blocked == should_block, reply)

    # 13 - the pin that would have caught it. Every recorded reply on this
    # machine, checked for a claim form the gate cannot see. The corpus is
    # this machine's own history and never travels with the repo, so on a
    # fresh clone this reports that it had nothing to read rather than
    # passing quietly.
    WORKSPACE = os.path.dirname(SYS)
    RESULT_LINE = _re.compile(r"^- \*\*Result:\*\*\s*(.+)$", _re.M)
    GENERATED = _re.compile(
        r"(?i)(?<![a-z])(" +
        "|".join(_re.escape(stem + e) for stem, es in FAMILIES.items()
                 for e in es) + r")(?![a-z])")
    replies, files = [], 0
    for dirpath, dirnames, names in os.walk(WORKSPACE):
        dirnames[:] = [d for d in dirnames
                       if d not in (".ai-system", ".git", "node_modules")]
        for n in names:
            p = os.path.join(dirpath, n)
            if n.startswith("CONTEXT-") and n.endswith(".md") and \
                    os.sep + ".claude-context" + os.sep in p:
                files += 1
                replies += RESULT_LINE.findall(
                    io.open(p, encoding="utf-8", errors="replace").read())
    if not files:
        ok("corpus pin: no recorded replies on this machine to check against",
           True, "0 CONTEXT files, nothing read")
    else:
        # A form the guard deliberately dropped is not a form the gate cannot
        # see, so the pin asks the exact question: is there a claim form that
        # SURVIVES the filters and is still unseen? Checked against all 18
        # suppressed replies by reading them, and every one is a job still
        # running, twelve of them in the masculine form that was blocking
        # honestly before this change.
        blind, suppressed = collections.Counter(), 0
        for line in replies:
            prose = gate.prose_only(line)
            if gate.find_claim(prose):
                continue
            for s in gate.SENTENCE.findall(prose):
                for m in GENERATED.finditer(s):
                    if gate.progress_report(s, m):
                        suppressed += 1
                    else:
                        blind[m.group(1).lower()] += 1
        ok("no recorded reply claims completion in a form the gate cannot see",
           not blind,
           ", ".join("%s x%d" % kv for kv in blind.most_common(6)) or
           "%d replies in %d files, %d progress reports correctly allowed"
           % (len(replies), files, suppressed))

    # 14 - running this system's own tools has to count as having looked.
    # The evidence list held five of twenty eight, all from the first week,
    # so the SEO, accessibility, performance, security, mail and parity
    # passes read as nothing checked. Pinned against the tools on disk rather
    # than a list in this file, so a tool added next month fails here until
    # somebody decides which kind it is.
    NOT_EVIDENCE = {
        "scaffold.py": "builds a site, it does not check one",
        "ogcard.py": "builds a share card",
        "clog.py": "writes the client log",
        "install.py": "installs; only --status reads, and that is listed",
        "install_hooks.py": "installs the hooks",
        "backfill.py": "rewrites history",
        "ctx.py": "mixed: rebuild, mode, rename and on/off all write",
        "ctxlib.py": "a library, never invoked on its own",
        "grouping.py": "a library, never invoked on its own",
        "hook_claim_gate.py": "a hook, run by the harness",
        "hook_stop.py": "a hook, run by the harness",
        "hook_session_start.py": "a hook, run by the harness",
        "hook_guard_write.py": "a hook, run by the harness",
    }
    unclassified, contradictory, counted = [], [], 0
    for dirpath, dirnames, names in os.walk(SYS):
        dirnames[:] = [d for d in dirnames
                       if d not in ("node_modules", "__pycache__", ".git",
                                    "vendor")]
        for n in sorted(names):
            if not n.endswith((".py", ".js")) or "test" in n.lower():
                continue
            runner = "node" if n.endswith(".js") else "python"
            cmd = '%s "%s"' % (runner, os.path.join(dirpath, n))
            evidence = bool(gate.EVIDENCE_BASH.search(cmd))
            if evidence:
                counted += 1
            if evidence and n in NOT_EVIDENCE:
                contradictory.append(n)
            elif not evidence and n not in NOT_EVIDENCE:
                unclassified.append(n)
    ok("every tool on disk is either evidence or named as not evidence",
       not unclassified, ", ".join(sorted(set(unclassified))) or
       "%d counted, %d deliberately not" % (counted, len(NOT_EVIDENCE)))
    ok("nothing is both counted as evidence and listed as not evidence",
       not contradictory, ", ".join(sorted(set(contradictory))) or "clean")

    for tool in ("seo.js", "a11y.js", "perf.js", "security.js", "analytics.js",
                 "mail.py", "parity.py", "job.py", "runtests.py"):
        ok("running %s counts as having checked something" % tool,
           bool(gate.EVIDENCE_BASH.search('node "x\\%s" https://y' % tool)))
    ok("python install.py --status still counts",
       bool(gate.EVIDENCE_BASH.search("python install.py --status")))
    ok("building a site is not checking it",
       not gate.EVIDENCE_BASH.search('python "x\\scaffold.py" --out y'))

    # 10 - never breaks the session
    bad = subprocess.run(
        [PY, "-X", "utf8", os.path.join(HERE, "hook_claim_gate.py")],
        input="not json", capture_output=True, text=True)
    ok("bad input -> exit 0, no output",
       bad.returncode == 0 and not bad.stdout.strip())

    reset()
    if saved is not None:
        io.open(state, "w", encoding="utf-8").write(saved)
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(TEST_FOLDER, ignore_errors=True)

    bad_n = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad_n, len(RESULTS)))
    return 1 if bad_n else 0


if __name__ == "__main__":
    sys.exit(main())
