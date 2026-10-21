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
