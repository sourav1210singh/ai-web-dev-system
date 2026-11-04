# -*- coding: utf-8 -*-
"""Does this system actually install somewhere other than where it was written?

The whole claim is that a clone works on another machine. The only way to
check that without another machine is to install into a different root with a
different home folder, and then look at what landed. Nothing here touches the
real ~/.claude or the real workspace.
"""
import io, json, os, shutil, subprocess, sys, tempfile

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
        shutil.copytree(HERE, sysdir, ignore=shutil.ignore_patterns(
            "__pycache__", ".git", "node_modules", "*.pyc"))
        ok("the system was cloned to another root", os.path.isdir(sysdir))

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
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
