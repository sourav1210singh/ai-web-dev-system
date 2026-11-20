# -*- coding: utf-8 -*-
"""Does this system actually install somewhere other than where it was written?

The whole claim is that a clone works on another machine. The only way to
check that without another machine is to install into a different root with a
different home folder, and then look at what landed. Nothing here touches the
real ~/.claude or the real workspace.
"""
import io, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def run(cmd, env=None, timeout=300):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          env=e)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tmp = tempfile.mkdtemp(prefix="installtest_")
    try:
        # a workspace that is deliberately not the one this was written in
        work = os.path.join(tmp, "Somewhere Else")
        home = os.path.join(tmp, "home")
        sysdir = os.path.join(work, ".ai-system")
        os.makedirs(home)
        # The second group are files the running system writes beside its own
        # code, and they are gitignored, so a real clone never has them. They
        # were being copied anyway, and the claim-gate hook rewrites
        # gate-state.json on every reply, so the copy raced the hook and this
        # suite failed with WinError 2 on a file that existed when the walk
        # began and not when the copy reached it. A flaky suite in a pre-push
        # gate is worse than no gate: it teaches you to re-run until green.
        shutil.copytree(HERE, sysdir, ignore=shutil.ignore_patterns(
            "__pycache__", ".git", "node_modules", "*.pyc",
            "gate-state.json", "hook.log", "runs.log", "audit.json",
            "audit.err", "inventory.json", "session_routes.json"))
        ok("the system was cloned to another root", os.path.isdir(sysdir))
        volatile = [f for f in ("gate-state.json", "hook.log", "runs.log")
                    if os.path.exists(os.path.join(sysdir, f))]
        ok("nothing the running system writes was cloned with it",
           not volatile, volatile or "a real clone has none of these either")

        env = {"USERPROFILE": home, "HOME": home, "HOMEDRIVE": "",
               "HOMEPATH": ""}
        p = run([sys.executable, "-X", "utf8",
                 os.path.join(sysdir, "install.py"), "--apply"], env)
        ok("install ran cleanly", p.returncode == 0,
           (p.stderr or p.stdout)[-200:])

        # --- the skills ---------------------------------------------------
        sk = os.path.join(home, ".claude", "skills")
        ok("skills landed under the new home", os.path.isdir(sk),
           sk if not os.path.isdir(sk) else "")
        installed = sorted(os.listdir(sk)) if os.path.isdir(sk) else []
        ok("every skill was installed", len(installed) >= 20, len(installed))

        doc = os.path.join(sk, "project-intake", "SKILL.md")
        text = io.open(doc, encoding="utf-8").read() if os.path.isfile(doc) else ""
        ok("the commands in a skill point at the new root",
           work in text, [l for l in text.splitlines()
                          if "python" in l and ".py" in l][:1])
        ok("no command still points at the folder it was written in",
           "C:\\Claude-Code" not in text,
           [l for l in text.splitlines() if "C:\\Claude-Code" in l][:1])

        # --- the context system -------------------------------------------
        ctx = os.path.join(work, ".context-system")
        ok("the context system was installed beside the projects",
           os.path.isfile(os.path.join(ctx, "ctxlib.py")), ctx)
        ok("its one-off migration scripts were not shipped",
           not os.path.isfile(os.path.join(ctx, "task4_move.py")))
        ok("no recorded data was shipped with it",
           not os.path.isfile(os.path.join(ctx, "runs.log")) and
           not os.path.isfile(os.path.join(ctx, "audit.json")))

        # The worklog sat in the installed copy only - untracked, unpublished,
        # one machine move from gone. An installer that silently drops a
        # subdirectory is the same failure wearing a different hat.
        wl = os.path.join(ctx, "worklog")
        ok("a subdirectory of the context system is installed too",
           os.path.isfile(os.path.join(wl, "timespent.py")) and
           os.path.isfile(os.path.join(wl, "estimate.py")), wl)
        io.open(os.path.join(wl, "keep.log"), "w", encoding="utf-8").write("history")
        io.open(os.path.join(sysdir, "context-system", "worklog", "keep.log"),
                "w", encoding="utf-8").write("stray")
        run([sys.executable, "-X", "utf8",
             os.path.join(sysdir, "install.py"), "--apply"], env)
        ok("recorded data inside a subdirectory is not overwritten either",
           io.open(os.path.join(wl, "keep.log"), encoding="utf-8").read()
           == "history")
        os.remove(os.path.join(sysdir, "context-system", "worklog", "keep.log"))

        # Running one of these tools from inside the repo leaves its log
        # beside it. Copying that over the installed one would replace a real
        # history with a stub: the install meant to keep the history would be
        # what destroyed it.
        io.open(os.path.join(ctx, "runs.log"), "w", encoding="utf-8").write(
            "a real history, many months of it")
        io.open(os.path.join(sysdir, "context-system", "runs.log"), "w",
                encoding="utf-8").write("stray")
        run([sys.executable, "-X", "utf8",
             os.path.join(sysdir, "install.py"), "--apply"], env)
        kept = io.open(os.path.join(ctx, "runs.log"), encoding="utf-8").read()
        ok("installing never overwrites recorded data with a stray copy",
           kept.startswith("a real history"), kept[:40])
        os.remove(os.path.join(sysdir, "context-system", "runs.log"))

        # --- the hooks ------------------------------------------------------
        sp = os.path.join(home, ".claude", "settings.json")
        cfg = json.loads(io.open(sp, encoding="utf-8").read()) \
            if os.path.isfile(sp) else {}
        entries = [(ev, h) for ev, gs in (cfg.get("hooks") or {}).items()
                   for g in gs for h in (g.get("hooks") or [])]
        ok("the hooks were registered in the new settings file",
           len(entries) == 4, len(entries))
        ok("every hook runs the interpreter that installed it",
           all(h.get("command") == sys.executable for _, h in entries),
           [h.get("command") for _, h in entries][:1])
        ok("every hook points inside the new root",
           all(work in (h.get("args") or [""])[-1] for _, h in entries),
           [(h.get("args") or [""])[-1] for _, h in entries][:1])
        ok("the claim gate is among them",
           any("claim_gate" in (h.get("args") or [""])[-1] for _, h in entries))

        # --- the part that was actually broken ------------------------------
        gate = os.path.join(sysdir, "hooks", "hook_claim_gate.py")
        g = run([sys.executable, "-X", "utf8", "-c",
                 "import runpy,sys;sys.argv=['x'];runpy.run_path(%r)" % gate],
                env)
        ok("the gate imports its helper from the new root, not a fixed one",
           "ModuleNotFoundError" not in (g.stderr or ""),
           (g.stderr or "").strip().splitlines()[-1:] or "clean")

        # --- settings that were already there are not destroyed -------------
        other = {"hooks": {"Stop": [{"hooks": [{"type": "command",
                                                "command": "echo",
                                                "_tag": "somebody-else"}]}]},
                 "theme": "dark"}
        io.open(sp, "w", encoding="utf-8").write(json.dumps(other))
        p = run([sys.executable, "-X", "utf8",
                 os.path.join(sysdir, "install.py"), "--apply"], env)
        cfg = json.loads(io.open(sp, encoding="utf-8").read())
        ok("an unrelated setting survives installation",
           cfg.get("theme") == "dark", cfg.get("theme"))
        tags = [h.get("_tag") for gs in (cfg.get("hooks") or {}).values()
                for g in gs for h in (g.get("hooks") or [])]
        ok("another tool's hook survives installation",
           "somebody-else" in tags, tags)
        ok("the settings file was backed up first",
           any(f.startswith("settings.json.bak-")
               for f in os.listdir(os.path.join(home, ".claude"))))

        # --- skills only ----------------------------------------------------
        io.open(sp, "w", encoding="utf-8").write("{}")
        p = run([sys.executable, "-X", "utf8",
                 os.path.join(sysdir, "install.py"), "--apply", "--no-hooks"],
                env)
        cfg = json.loads(io.open(sp, encoding="utf-8").read())
        ok("--no-hooks leaves the settings file alone",
           not cfg.get("hooks"), cfg)

        # --- no code may carry the folder it was written in ------------------
        # Six files held one of these and every one of them failed quietly on
        # another machine rather than loudly: leakcheck.py compared the repo
        # against an empty client list and reported CLEAN, and the guard on
        # stray writes watched a home directory belonging to nobody. Nothing
        # in the suite looked, because installtest checked one skill document
        # and no code at all.
        #
        # The needles come from install.py's own constant, so there is one
        # definition of "the folder this was written in" and not two.
        sys.path.insert(0, sysdir)
        import importlib
        inst = importlib.import_module("install")
        importlib.reload(inst)
        authored = inst.AUTHORED_ROOT.decode("utf-8")
        flat = authored.replace(":", "-").replace("\\", "-")
        home_literal = os.path.join("C:\\", "Users", "admin")
        needles = (authored, authored.replace("\\", "/"), flat, home_literal,
                   home_literal.replace("\\", "/"))
        # A module-level constant holding a machine's own path is the bug.
        # The same string in a comment explaining the bug, or indented as a
        # test fixture, is not, so this matches an assignment at column zero
        # and not a mention.
        ASSIGN = re.compile(r"(?m)^[A-Za-z_][A-Za-z0-9_]*\s*=[^\n]*(" +
                            "|".join(re.escape(n) for n in needles) + r")")
        ALLOWED = {"install.py": "AUTHORED_ROOT is the string being rewritten"}
        offenders, scanned = [], 0
        for base in (sysdir, ctx, sk):
            for dirpath, dirnames, names in os.walk(base):
                dirnames[:] = [d for d in dirnames
                               if d not in ("node_modules", "__pycache__",
                                            ".git", "vendor")]
                for n in sorted(names):
                    if not n.endswith((".py", ".js")):
                        continue
                    scanned += 1
                    body = io.open(os.path.join(dirpath, n), encoding="utf-8",
                                   errors="replace").read()
                    m = ASSIGN.search(body)
                    if m and n not in ALLOWED:
                        offenders.append("%s: %s" % (n, m.group(0).strip()[:60]))
        ok("no installed code assigns the folder it was written in",
           not offenders, "; ".join(sorted(set(offenders))[:4]) or
           "%d files scanned" % scanned)
        ok("install.py still carries the one string that is meant to be there",
           isinstance(inst.AUTHORED_ROOT, bytes) and authored,
           "%s (%s)" % (authored, ALLOWED["install.py"]))

        # Reading the text is not enough and the fix that prompted this proves
        # it: the guard built its path with os.path.join("C:\\", "Users",
        # "admin"), so there was no literal in the file to find. The only
        # honest check is where these values actually point when the code runs
        # from the clone.
        def resolve(label, pathdir, code):
            p = run([sys.executable, "-X", "utf8", "-c",
                     "import sys;sys.path.insert(0,%r);%s" % (pathdir, code)],
                    env)
            return label, (p.stdout or "").strip(), (p.stderr or "").strip()

        probes = [
            resolve("leakcheck's client root", sysdir,
                    "import leakcheck;print(leakcheck.ROOT)"),
            resolve("clog's client root",
                    os.path.join(sysdir, "skills", "client-log"),
                    "import clog;print(clog.ROOT)"),
            resolve("the context system's workspace", ctx,
                    "import ctxlib;print(ctxlib.ROOT)"),
        ]
        for label, got, err in probes:
            ok("%s resolves inside the clone" % label,
               got and os.path.normcase(got) == os.path.normcase(work),
               got or err[-120:])

        label, flatgot, err = resolve("prefix", ctx,
                                      "import ctxlib;print(ctxlib.PREFIX)")
        ok("the transcript prefix follows the workspace, not the author's",
           flatgot and flatgot != flat, "%s vs authored %s" % (flatgot, flat))
        # These two do opposite jobs, so they are checked in opposite
        # directions. memcheck builds the transcript directory name and has to
        # use this workspace's prefix. range strips it, and the proof that it
        # used the right one is that nothing of the prefix is left behind.
        _l, got, err = resolve("memcheck", ctx,
                               "import memcheck;print(memcheck.sanitise('X'))")
        ok("memcheck names the transcript directory after THIS workspace",
           got.startswith(flatgot.replace(" ", "-")) and flat not in got,
           got or err[-140:])

        _l, got, err = resolve(
            "range", os.path.join(ctx, "worklog"),
            "import importlib;r=importlib.import_module('range');"
            "print(r.unsanitise('%s-X'))" % flatgot)
        ok("the worklog strips this workspace's prefix, leaving the folder",
           got == "X", got or err[-140:])

        # And the guard's stray list has to be this user's, not a remembered
        # one. The check that catches the assembled form.
        g = run([sys.executable, "-X", "utf8", "-c",
                 "import sys;sys.path.insert(0,%r);"
                 "import hook_guard_write as h;print(chr(10).join(h.STRAY))"
                 % ctx], env)
        stray = [l for l in (g.stdout or "").splitlines() if l.strip()]
        ok("the stray-write guard watches the home it is running under",
           stray and all(l.lower().startswith(home.lower()) for l in stray),
           "; ".join(stray[:2]) or (g.stderr or "")[-120:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
