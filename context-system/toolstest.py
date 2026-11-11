# -*- coding: utf-8 -*-
"""The context system's own tools, which had no suite at all.

audit.py, audit_report.py, memcheck.py, grouping.py, worklog/range.py and
install_hooks.py were all measured on 11 Nov as named by no test. selftest.py
drives the recorder end to end and never touches these, so a change to any of
them would have been caught by nothing.

Every fixture here is built from a shape read off disk or out of the function
under test, never from a recollection of what it probably looks like: a
fixture written from memory tests the memory.
"""
import io, json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "worklog"))
import ctxlib as c
import audit, audit_report, grouping, memcheck
import range as daterange

PY = sys.executable
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def row(session_id, title, first_prompt, prompts, first_ts, last_ts,
        project_dir="C--Claude-Code-Demo"):
    """One inventory row, with the keys a real inventory.json carries."""
    return {"session_id": session_id, "project_dir": project_dir,
            "custom_title": None, "ai_title": title,
            "first_prompt": first_prompt, "last_prompt": first_prompt,
            "human_prompts": prompts, "assistant_msgs": prompts,
            "first_ts": first_ts, "last_ts": last_ts,
            "cwd": "C:\\Claude-Code\\Demo", "path": "x.jsonl", "bytes": 10}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tmp = tempfile.mkdtemp(prefix="toolstest_")
    try:
        # ---------------------------------------------- audit.py: writes_in
        # It reads transcripts line by line and must survive everything a
        # real one contains: user turns, tool calls that are not writes, and
        # a half-written line, which happens when a session is still running.
        t = os.path.join(tmp, "t.jsonl")
        lines = [
            json.dumps({"type": "user", "timestamp": "2026-11-01T10:00:00Z",
                        "message": {"role": "user", "content": "do it"}}),
            json.dumps({"type": "assistant", "timestamp": "2026-11-01T10:00:01Z",
                        "message": {"role": "assistant", "content": [
                            {"type": "text", "text": "ok"},
                            {"type": "tool_use", "name": "Write",
                             "input": {"file_path": "C:\\Claude-Code\\Demo\\a.md"}},
                            {"type": "tool_use", "name": "Edit",
                             "input": {"file_path": "C:/Claude-Code/Demo/b.md"}},
                            {"type": "tool_use", "name": "Bash",
                             "input": {"command": "echo hi"}}]}}),
            '{"type":"assistant","message":{"content":[{"type":"tool_use"',
        ]
        io.open(t, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        got = audit.writes_in(t)
        ok("every written path is collected", len(got) == 2, sorted(got))
        ok("the paths are normalised, so one file is not counted as two",
           os.path.normpath("C:\\Claude-Code\\Demo\\b.md") in got, sorted(got))
        ok("a command that wrote nothing is not counted as a write",
           not any("echo" in p for p in got))
        ok("a half-written line does not stop the read", len(got) == 2)

        # ------------------------------------------ audit: top_folder
        for mod in (audit, audit_report):
            name = mod.__name__
            inside = os.path.join(c.ROOT, "Some Client", "deep", "file.md")
            ok("%s puts a file under the folder that owns it" % name,
               mod.top_folder(inside) == "Some Client", mod.top_folder(inside))
            ok("%s returns nothing for a path outside the workspace" % name,
               mod.top_folder(r"D:\elsewhere\file.md") is None)
            ok("%s returns nothing for the workspace root itself" % name,
               mod.top_folder(c.ROOT) is None, mod.top_folder(c.ROOT))

        # ---------------------------------------------------- grouping.py
        ok("a signature ignores case and spacing",
           grouping.norm_sig("  Make  THE Hero \n fit ") ==
           grouping.norm_sig("make the hero fit"),
           grouping.norm_sig("  Make  THE Hero \n fit "))
        ok("a signature is cut to a fixed length",
           len(grouping.norm_sig("x " * 400)) <= 120)

        # R2: a forked session keeps the same opening prompt under a new
        # title, and must not become a second project.
        forked = grouping.group_folder([
            row("aaaaaaaa", "Blog fixes", "fix the blog please", 10,
                "2026-10-01T09:00:00Z", "2026-10-01T10:00:00Z"),
            row("bbbbbbbb", "Something else entirely", "fix the blog please", 3,
                "2026-10-02T09:00:00Z", "2026-10-02T10:00:00Z"),
        ])
        ok("two sessions with the same opening prompt are one project",
           len(forked) == 1, [g["slug"] for g in forked])
        ok("the merged project keeps every session",
           forked and len(forked[0]["sessions"]) == 2)
        ok("its prompts are added up", forked and forked[0]["prompts"] == 13,
           forked[0]["prompts"] if forked else "-")
        ok("the busier title wins the label",
           forked and forked[0]["label"] == "Blog fixes",
           forked[0]["label"] if forked else "-")
        ok("the span runs from the earliest to the latest",
           forked and forked[0]["first"].startswith("2026-10-01") and
           forked[0]["last"].startswith("2026-10-02"))

        # R3: one slug being a prefix of another is the same work renamed
        prefixed = grouping.group_folder([
            row("cccccccc", "Hero", "first thing", 5,
                "2026-10-01T09:00:00Z", "2026-10-01T10:00:00Z"),
            row("dddddddd", "Hero rebuild", "a different opening", 2,
                "2026-10-02T09:00:00Z", "2026-10-02T10:00:00Z"),
        ])
        ok("a longer slug under a shorter one is the same project",
           len(prefixed) == 1, [g["slug"] for g in prefixed])

        separate = grouping.group_folder([
            row("eeeeeeee", "Hero", "first thing", 5,
                "2026-10-01T09:00:00Z", "2026-10-01T10:00:00Z"),
            row("ffffffff", "Mail deliverability", "a different opening", 2,
                "2026-10-02T09:00:00Z", "2026-10-02T10:00:00Z"),
        ])
        ok("unrelated work stays two projects", len(separate) == 2,
           [g["slug"] for g in separate])
        ok("the busier project is listed first",
           separate and separate[0]["prompts"] >= separate[-1]["prompts"])

        # folder_path_for: Claude Code flattens the working directory, and a
        # folder name with a space in it comes back with a hyphen.
        spaced = os.path.join(c.ROOT, "_toolstest folder")
        os.makedirs(spaced, exist_ok=True)
        try:
            pdir = grouping.PREFIX + "-_toolstest-folder"
            ok("a flattened directory name finds the folder it means",
               grouping.folder_path_for(pdir) == spaced,
               grouping.folder_path_for(pdir))
            ok("a directory name matching no folder returns nothing",
               grouping.folder_path_for(grouping.PREFIX + "-no-such-folder")
               is None)
            ok("the workspace's own name resolves to the workspace",
               grouping.folder_path_for(grouping.PREFIX) == grouping.ROOT)
        finally:
            shutil.rmtree(spaced, ignore_errors=True)

        # ---------------------------------------------------- memcheck.py
        ok("a folder name becomes the transcript directory name",
           memcheck.sanitise("Some Client") == "C--Claude-Code-Some-Client",
           memcheck.sanitise("Some Client"))
        empty = os.path.join(tmp, "empty")
        os.makedirs(empty)
        ok("an empty directory has no newest file", memcheck.newest(empty) == 0)
        ok("a directory that does not exist is not an error",
           memcheck.newest(os.path.join(tmp, "nope")) == 0)
        f = os.path.join(empty, "a.md")
        io.open(f, "w", encoding="utf-8").write("x")
        ok("a file in it is found", memcheck.newest(empty) > 0)
        ok("nothing written reads as a dash", memcheck.ago(0) == "-")
        ok("minutes, hours and days are told apart",
           memcheck.ago(time.time() - 600).endswith("m ago") and
           memcheck.ago(time.time() - 7200).endswith("h ago") and
           memcheck.ago(time.time() - 200000).endswith("d ago"),
           "%s / %s / %s" % (memcheck.ago(time.time() - 600),
                             memcheck.ago(time.time() - 7200),
                             memcheck.ago(time.time() - 200000)))

        # ------------------------------------------------ worklog/range.py
        ok("a flattened name reads back as the folder",
           daterange.unsanitise("C--Claude-Code-Some-Project") == "Some Project",
           daterange.unsanitise("C--Claude-Code-Some-Project"))
        ok("the workspace root is named rather than left blank",
           daterange.unsanitise("C--Claude-Code") == "(root) Claude-Code",
           daterange.unsanitise("C--Claude-Code"))
        ok("a plain string message is its own text",
           daterange.text_of({"content": "hello"}) == "hello")
        ok("a block message keeps only the text blocks",
           daterange.text_of({"content": [
               {"type": "text", "text": "one"},
               {"type": "tool_use", "name": "Write", "input": {}},
               {"type": "text", "text": "two"}]}) == "one\ntwo")
        ok("a message with nothing in it is empty, not an error",
           daterange.text_of({}) == "")

        # --------------------------------------------- install_hooks.py
        # The installer that owns settings.json. --remove was the part no
        # test had ever run, and it is the one that could take somebody
        # else's hooks away with ours.
        # Run the copy in THIS repo, not the installed one. Pointing a suite
        # at the installed copy means a change to the file being committed is
        # tested by nothing until somebody remembers to run install.py, and a
        # mutation test proved exactly that: breaking this file changed no
        # result at all.
        src = HERE
        home = os.path.join(tmp, "home")
        os.makedirs(os.path.join(home, ".claude"))
        sp = os.path.join(home, ".claude", "settings.json")
        io.open(sp, "w", encoding="utf-8").write(json.dumps({
            "theme": "dark",
            "hooks": {"Stop": [{"hooks": [{"type": "command",
                                           "command": "echo",
                                           "_tag": "somebody-else"}]}]}}))
        env = dict(os.environ)
        env.update({"USERPROFILE": home, "HOME": home, "HOMEDRIVE": "",
                    "HOMEPATH": ""})

        def hooks_now():
            cfg = json.loads(io.open(sp, encoding="utf-8").read())
            return [(ev, h) for ev, gs in (cfg.get("hooks") or {}).items()
                    for g in gs for h in (g.get("hooks") or [])]

        def run_installer(*args):
            return subprocess.run(
                [PY, "-X", "utf8", os.path.join(src, "install_hooks.py")]
                + list(args), capture_output=True, text=True, env=env,
                timeout=120)

        p = run_installer()
        ok("the hook installer runs cleanly", p.returncode == 0,
           (p.stderr or "")[-120:])
        ours = [h for _, h in hooks_now() if h.get("_tag") == "claude-context-system"]
        ok("it registers its own hooks", len(ours) >= 2, len(ours))
        ok("somebody else's hook survives installation",
           any(h.get("_tag") == "somebody-else" for _, h in hooks_now()))
        # A hook registered at a path that does not exist never runs and
        # never says so. This caught the claim gate being registered at
        # <workspace>\.ai-system\.ai-system\hooks whenever install_hooks.py
        # was run the way its own docstring says to.
        missing = [(h.get("args") or [""])[-1] for h in ours
                   if not os.path.isfile((h.get("args") or [""])[-1])]
        ok("every hook it registers points at a file that exists",
           not missing, ", ".join(missing) or "%d paths" % len(ours))
        ok("the claim gate is one of them",
           any("hook_claim_gate" in (h.get("args") or [""])[-1] for h in ours))

        p = run_installer("--remove")
        ok("--remove runs cleanly", p.returncode == 0, (p.stderr or "")[-120:])
        left = hooks_now()
        ok("--remove takes our hooks out",
           not [h for _, h in left if h.get("_tag") == "claude-context-system"],
           len(left))
        ok("--remove leaves somebody else's hook alone",
           any(h.get("_tag") == "somebody-else" for _, h in left),
           [h.get("_tag") for _, h in left])
        cfg = json.loads(io.open(sp, encoding="utf-8").read())
        ok("an unrelated setting is not lost on the way out",
           cfg.get("theme") == "dark", cfg.get("theme"))
        ok("the settings file was backed up before either change",
           any(f.startswith("settings.json.bak-")
               for f in os.listdir(os.path.join(home, ".claude"))))

        # ------------------------------------------------------- ctx.py
        p = subprocess.run([PY, "-X", "utf8", os.path.join(src, "ctx.py"),
                            "nonsense"], capture_output=True, text=True,
                           timeout=120)
        ok("an unknown command prints the control panel rather than a stack",
           "python ctx.py status" in (p.stdout or "") and
           "Traceback" not in (p.stderr or ""), (p.stderr or "")[-80:])
        p = subprocess.run([PY, "-X", "utf8", os.path.join(src, "ctx.py"),
                            "status"], capture_output=True, text=True,
                           timeout=180)
        ok("status reports without failing", p.returncode == 0,
           (p.stderr or "")[-120:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
