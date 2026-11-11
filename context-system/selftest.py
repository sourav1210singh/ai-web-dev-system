# -*- coding: utf-8 -*-
"""End-to-end test of the context system against a throwaway project folder."""
import io, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctxlib as c

ROOT = c.ROOT
TEST = os.path.join(ROOT, "_ctxtest")
TRANS = os.path.join(HERE, "_test_transcripts")
PY = sys.executable
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append((bool(cond), name, extra))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def turn(ts, prompt, reply, files=()):
    out = [json.dumps({"type": "user", "origin": {"kind": "human"},
                       "timestamp": ts, "sessionId": "x",
                       "message": {"role": "user", "content": prompt}})]
    content = [{"type": "text", "text": reply}]
    for f in files:
        content.append({"type": "tool_use", "name": "Write",
                        "input": {"file_path": f, "content": "x"}})
    out.append(json.dumps({"type": "assistant", "timestamp": ts,
                           "message": {"role": "assistant", "content": content}}))
    return "\n".join(out) + "\n"


def make_transcript(path, title, turns):
    body = json.dumps({"type": "ai-title", "aiTitle": title}) + "\n"
    for t in turns:
        body += t
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)


def run_hook(script, payload):
    p = subprocess.run([PY, "-X", "utf8", os.path.join(HERE, script)],
                       input=json.dumps(payload), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def entries(path):
    return c.read(path).count("\n### ")


def main():
    for d in (TEST, TRANS):
        shutil.rmtree(d, ignore_errors=True)
    os.makedirs(os.path.join(TEST, "subdir", "deeper"))
    os.makedirs(TRANS)

    tA = os.path.join(TRANS, "sessA.jsonl")
    tB = os.path.join(TRANS, "sessB.jsonl")
    make_transcript(tA, "Alpha Client Site", [
        turn("2026-10-09T10:00:00.000Z", "alpha: build the homepage", "Homepage built.",
             [os.path.join(TEST, "home.html")])])
    make_transcript(tB, "Beta Client Shop", [
        turn("2026-10-09T11:00:00.000Z", "beta: fix the cart", "Cart fixed.")])

    base = c.ctx_dir_for(TEST)

    # ---------------------------------------------------------- 1. single mode
    c.save_config(TEST, {"mode": "single", "project": "Alpha Client Site"})
    rc, _, err = run_hook("hook_stop.py", {
        "session_id": "sessA", "transcript_path": tA, "cwd": TEST,
        "hook_event_name": "Stop"})
    f = os.path.join(base, "CONTEXT-01.md")
    ok("single: hook exits 0", rc == 0, err.strip()[:120])
    ok("single: CONTEXT-01.md created", os.path.isfile(f))
    ok("single: entry appended", entries(f) == 1, "entries=%d" % entries(f))
    ok("single: prompt text recorded", "alpha: build the homepage" in c.read(f))
    ok("single: result recorded", "Homepage built." in c.read(f))
    ok("single: edited file recorded", "home.html" in c.read(f))

    # -------------------------------------------- 2. cwd in a nested subfolder
    make_transcript(tA, "Alpha Client Site", [
        turn("2026-10-09T10:00:00.000Z", "alpha: build the homepage", "Homepage built."),
        turn("2026-10-09T10:05:00.000Z", "alpha: add a contact form", "Form added.")])
    rc, _, _ = run_hook("hook_stop.py", {
        "session_id": "sessA", "transcript_path": tA,
        "cwd": os.path.join(TEST, "subdir", "deeper"), "hook_event_name": "Stop"})
    ok("nested cwd routes to the project folder", entries(f) == 2,
       "entries=%d" % entries(f))

    # ---------------------------------------------------------- 3. duplicates
    for _ in range(3):
        run_hook("hook_stop.py", {"session_id": "sessA", "transcript_path": tA,
                                  "cwd": TEST, "hook_event_name": "Stop"})
    ok("repeat runs add no duplicate", entries(f) == 2, "entries=%d" % entries(f))

    # ----------------------------------------------------------- 4. multi mode
    shutil.rmtree(base, ignore_errors=True)
    c.save_config(TEST, {"mode": "multi", "map": {}, "labels": {}})
    run_hook("hook_stop.py", {"session_id": "sessA", "transcript_path": tA,
                              "cwd": TEST, "hook_event_name": "Stop"})
    run_hook("hook_stop.py", {"session_id": "sessB", "transcript_path": tB,
                              "cwd": TEST, "hook_event_name": "Stop"})
    fa = os.path.join(base, "alpha-client-site", "CONTEXT-01.md")
    fb = os.path.join(base, "beta-client-shop", "CONTEXT-01.md")
    ok("multi: project A has its own folder", os.path.isfile(fa))
    ok("multi: project B has its own folder", os.path.isfile(fb))
    ok("multi: A holds only A's work",
       "alpha: add a contact form" in c.read(fa) and "beta:" not in c.read(fa))
    ok("multi: B holds only B's work",
       "beta: fix the cart" in c.read(fb) and "alpha:" not in c.read(fb))
    cfg = c.load_config(TEST)
    ok("multi: session->project map saved",
       cfg.get("map", {}).get("sessA") == "alpha-client-site"
       and cfg.get("map", {}).get("sessB") == "beta-client-shop",
       json.dumps(cfg.get("map", {})))

    # -------------------------------------------------------------- 5. index
    idx = os.path.join(base, "INDEX.md")
    ok("INDEX.md lists both projects",
       os.path.isfile(idx) and "Alpha Client Site" in c.read(idx)
       and "Beta Client Shop" in c.read(idx))

    # ------------------------------------------------- 6. rotation at 10k words
    big = {"ts": "2026-10-09T12:00:00.000Z", "p": " ".join(["filler"] * 300),
           "a": "", "files": []}
    from backfill import entry_md
    for i in range(300):          # entries are capped at ~40 words each
        big["ts"] = "2026-10-09T12:%02d:%02d.000Z" % (i // 60, i % 60)
        c.append_entry(os.path.dirname(fa), entry_md(big), TEST, "Alpha", "2026-10-09")
    files = c.list_context_files(os.path.dirname(fa))
    worst = max(c.count_words(c.read(x)) for x in files)
    ok("rotation: more than one CONTEXT file", len(files) > 1,
       ", ".join(os.path.basename(x) for x in files))
    ok("rotation: no file exceeds %d words" % c.WORD_LIMIT, worst <= c.WORD_LIMIT,
       "largest=%d" % worst)

    # --------------------------------------------------- 7. SessionStart hook
    rc, out, err = run_hook("hook_session_start.py", {
        "cwd": TEST, "hook_event_name": "SessionStart", "source": "startup"})
    ok("SessionStart exits 0", rc == 0, err.strip()[:120])
    try:
        j = json.loads(out) if out.strip() else {}
    except Exception as e:
        j = {}
        ok("SessionStart emits valid JSON", False, str(e))
    else:
        ok("SessionStart emits valid JSON", True)
    ctx = (j.get("hookSpecificOutput") or {}).get("additionalContext", "")
    ok("SessionStart injects the index",
       "Alpha Client Site" in ctx and "Beta Client Shop" in ctx,
       "%d chars" % len(ctx))

    # ---------------- 7b. a chat started before a move still lands correctly
    newhome = os.path.join(ROOT, "_ctxtest_moved")
    shutil.rmtree(newhome, ignore_errors=True)
    os.makedirs(newhome)
    routes_path = os.path.join(HERE, "session_routes.json")
    saved = c.read(routes_path) if os.path.isfile(routes_path) else None
    c.write(routes_path, json.dumps({"sessB": {
        "folder": newhome, "slug": "", "label": "Beta Client Shop",
        "moved_from": "C--Claude-Code-_ctxtest"}}))
    c.save_config(newhome, {"mode": "single", "project": "Beta Client Shop"})
    run_hook("hook_stop.py", {"session_id": "sessB", "transcript_path": tB,
                              "cwd": TEST, "hook_event_name": "Stop"})
    rf = os.path.join(c.ctx_dir_for(newhome), "CONTEXT-01.md")
    ok("moved project: old chat writes to the new folder", os.path.isfile(rf))
    ok("moved project: nothing added back in the old folder",
       "beta: fix the cart" not in c.read(fb) or entries(fb) == 1,
       "old-folder entries=%d" % entries(fb))
    rc, out, _ = run_hook("hook_session_start.py", {
        "session_id": "sessB", "cwd": TEST,
        "hook_event_name": "SessionStart", "source": "resume"})
    j2 = json.loads(out) if out.strip() else {}
    ctx2 = (j2.get("hookSpecificOutput") or {}).get("additionalContext", "")
    ok("moved project: session start says it moved",
       "has moved" in ctx2 and newhome in ctx2)
    if saved is None:
        os.remove(routes_path)
    else:
        c.write(routes_path, saved)
    shutil.rmtree(newhome, ignore_errors=True)

    # ------------------------------------------- 8. outside the root is ignored
    rc, out, _ = run_hook("hook_stop.py", {
        "session_id": "sessA", "transcript_path": tA,
        "cwd": os.path.join(os.environ.get("TEMP", "C:\\Temp")),
        "hook_event_name": "Stop"})
    ok("cwd outside C:\\Claude-Code is ignored", rc == 0 and not out.strip())

    # -------------------------- 8b. a folder added later sets itself up alone
    fresh = os.path.join(ROOT, "_ctxtest_new")
    shutil.rmtree(fresh, ignore_errors=True)
    os.makedirs(fresh)
    run_hook("hook_stop.py", {"session_id": "sessNew", "transcript_path": tB,
                              "cwd": fresh, "hook_event_name": "Stop"})
    nf = os.path.join(c.ctx_dir_for(fresh), "CONTEXT-01.md")
    ok("new folder: context created with no setup", os.path.isfile(nf))
    ok("new folder: CLAUDE.md pointer written",
       os.path.isfile(os.path.join(fresh, "CLAUDE.md")))
    ok("new folder: defaults to single mode",
       (c.load_config(fresh).get("mode")) == "single",
       str(c.load_config(fresh).get("mode")))
    shutil.rmtree(fresh, ignore_errors=True)

    # ------------------------------------------------------- 9. bad input safety
    for bad in ["", "not json", "{}", '{"cwd":"C:\\\\nope"}']:
        p = subprocess.run([PY, "-X", "utf8", os.path.join(HERE, "hook_stop.py")],
                           input=bad, capture_output=True, text=True)
        if p.returncode != 0:
            ok("bad input never breaks the session (%r)" % bad[:12], False)
            break
    else:
        ok("bad input never breaks the session", True)

    # ---------------------------------------------- 10. the working rules
    # The rules template was correct and sat in 0 of 24 project folders,
    # because it was written for a NEW project to be given and nothing ever
    # reached the ones that already existed. It has its own marker block now,
    # on the same contract as the context pointer: inside the markers is ours
    # and kept current, outside is the user's and survives untouched.
    import backfill
    rules = os.path.join(TEST, "_rules")
    os.makedirs(rules, exist_ok=True)
    md = os.path.join(rules, "CLAUDE.md")

    body = backfill.rules_text()
    ok("the rules template is found from the installed copy", bool(body.strip()),
       "%d chars" % len(body))

    # a) a folder with nothing in it
    backfill.install_rules_md(rules)
    got = c.read(md)
    ok("a folder with no CLAUDE.md gets one with the rules",
       backfill.RULES_BEGIN in got and "No false statements" in got)
    ok("with no context block, the history section is kept",
       "INDEX.md" in got)

    # b) the context block goes in beside it, and neither eats the other
    backfill.install_claude_md(rules, "single",
                               [{"label": "Rules test", "slug": ""}])
    got = c.read(md)
    ok("installing the context pointer leaves the rules block alone",
       backfill.RULES_BEGIN in got and backfill.MARK_BEGIN in got)

    # c) refreshed beside a context block, the duplicated half is dropped
    backfill.install_rules_md(rules)
    got = c.read(md)
    ok("beside a context block the repeated half is dropped",
       got.count("`.claude-context/INDEX.md` lists what exists") == 0, "")
    ok("but the rules in that same section survive the drop",
       "Never substitute your own memory" in got)
    ok("and the marker that did the dropping is not left in the file",
       "only-without-context-system" not in got)
    ok("the cut does not leave a heading with two blank lines under it",
       "\n\n\n" not in got, repr(got[got.find("## Read this"):][:70]))

    # d) the user's own text survives, and a second run changes nothing
    c.write(md, c.read(md).rstrip() + "\n\n## My own note\n\nKeep this.\n")
    before = c.read(md)
    backfill.install_rules_md(rules)
    backfill.install_rules_md(rules)
    after = c.read(md)
    ok("text outside both blocks survives", "## My own note" in after and
       "Keep this." in after)
    ok("running it again changes nothing", after == before, "idempotent")
    ok("the rules block is not duplicated",
       after.count(backfill.RULES_BEGIN) == 1,
       "%d blocks" % after.count(backfill.RULES_BEGIN))

    # e) an edit inside the block is ours to overwrite, which is the contract
    c.write(md, c.read(md).replace("No false statements", "SOMETHING ELSE"))
    backfill.install_rules_md(rules)
    ok("an edit inside the block is restored from the template",
       "No false statements" in c.read(md))

    # f) and the recorder itself installs them, which is what reaches the
    # folders nobody will run a command in
    folder_md = os.path.join(TEST, "CLAUDE.md")
    if os.path.isfile(folder_md):
        ok("the recorder put the rules into the project folder it recorded",
           backfill.RULES_BEGIN in c.read(folder_md),
           "block present" if backfill.RULES_BEGIN in c.read(folder_md)
           else "missing")

    # ------------------------------------------- 11. the guard on stray writes
    # The only one of the four hooks with no test, and the one that exists
    # because a script once wrote over every project's context. It warns and
    # never blocks, so the thing to pin is what it notices and what it
    # correctly stays quiet about.
    import hook_guard_write as guard

    def guarded(path, cwd=TEST, response=False):
        payload = {"session_id": "guard-test", "cwd": cwd,
                   "hook_event_name": "PostToolUse", "tool_name": "Write"}
        if response:
            payload["tool_response"] = {"filePath": path}
        else:
            payload["tool_input"] = {"file_path": path}
        rc, out, err = run_hook("hook_guard_write.py", payload)
        msg = ""
        if out.strip():
            try:
                msg = json.loads(out).get("systemMessage", "")
            except Exception:
                msg = "UNPARSEABLE: " + out[:80]
        return rc, msg

    ok("the guard knows where stray files land", bool(guard.STRAY),
       ", ".join(os.path.basename(s) for s in guard.STRAY))

    for stray in guard.STRAY:
        rc, msg = guarded(os.path.join(stray, "report.md"))
        if "outside the project" not in msg:
            ok("a file saved to %s is flagged" % os.path.basename(stray),
               False, msg[:60] or "silent")
            break
    else:
        ok("a file saved anywhere outside the project is flagged", True,
           "%d locations" % len(guard.STRAY))

    rc, msg = guarded(os.path.join(TEST, "deliverable.md"))
    ok("a file saved inside the project is not flagged", not msg, msg[:60])

    other = os.path.join(ROOT, "_ctxtest_other")
    os.makedirs(other, exist_ok=True)
    rc, msg = guarded(os.path.join(other, "notes.md"))
    ok("writing into another project's folder is flagged",
       "another project" in msg and "_ctxtest_other" in msg, msg[:70])
    shutil.rmtree(other, ignore_errors=True)

    rc, msg = guarded(os.path.join(c.ROOT, ".context-system", "runs.log"))
    ok("the context system writing beside itself is not another project",
       not msg, msg[:60])

    for quiet in (os.path.join(os.environ.get("TEMP", "C:\\Windows\\Temp"),
                               "scratch.md"),
                  os.path.join(TEST, "node_modules", "x", "index.js"),
                  os.path.join(TEST, ".git", "COMMIT_EDITMSG")):
        rc, msg = guarded(quiet)
        if msg:
            ok("throwaway and machinery paths are ignored", False,
               "%s -> %s" % (quiet[-30:], msg[:40]))
            break
    else:
        ok("throwaway and machinery paths are ignored", True,
           "temp, node_modules, .git")

    rc, msg = guarded(os.path.join(guard.STRAY[0], "from-response.md"),
                      response=True)
    ok("the path is read from the tool's response as well as its input",
       "outside the project" in msg, msg[:60] or "silent")

    rc, out, err = run_hook("hook_guard_write.py",
                            {"session_id": "guard-test", "cwd": TEST,
                             "tool_input": {}})
    ok("a tool call with no file path is ignored", not out.strip(), out[:60])

    for bad_in in ["", "not json", "{}"]:
        p = subprocess.run([PY, "-X", "utf8",
                            os.path.join(HERE, "hook_guard_write.py")],
                           input=bad_in, capture_output=True, text=True)
        if p.returncode != 0:
            ok("the guard never breaks the session (%r)" % bad_in[:10], False,
               p.stderr[-60:])
            break
    else:
        ok("the guard never breaks the session", True)

    shutil.rmtree(TEST, ignore_errors=True)
    shutil.rmtree(TRANS, ignore_errors=True)

    bad = [r for r in RESULTS if not r[0]]
    print("\n%d/%d checks passed" % (len(RESULTS) - len(bad), len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
