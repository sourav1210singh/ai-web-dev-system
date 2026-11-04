# -*- coding: utf-8 -*-
"""Control panel for the project context system.

  python ctx.py status                     what exists right now
  python ctx.py rebuild [folder-name]      rebuild from the transcripts
  python ctx.py mode <folder> single|multi switch a folder between one/many projects
  python ctx.py rename <folder> <slug> "New name"
  python ctx.py check                      verify every file
  python ctx.py audit                      find files sitting in the wrong folder
  python ctx.py memcheck                   is auto-memory landing inside the projects?
  python ctx.py prompts                    regenerate the paste-into-chat prompts
  python ctx.py on | off                   turn the automatic recording on/off
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctxlib as c

PY = sys.executable


def run(script, *args):
    return subprocess.call([PY, "-X", "utf8", os.path.join(HERE, script)] + list(args))


def find_folder(name):
    for d in os.listdir(c.ROOT):
        p = os.path.join(c.ROOT, d)
        if os.path.isdir(p) and d.lower() == name.lower():
            return p
    for d in os.listdir(c.ROOT):
        p = os.path.join(c.ROOT, d)
        if os.path.isdir(p) and name.lower() in d.lower():
            return p
    return None


def cmd_status():
    print("%-26s %-6s %-34s %5s %9s" % ("FOLDER", "MODE", "PROJECT", "FILES", "WORDS"))
    tot = [0, 0, 0]
    for d in sorted(os.listdir(c.ROOT)):
        folder = os.path.join(c.ROOT, d)
        if not os.path.isdir(folder):
            continue
        streams = c.project_streams(folder)
        if not streams:
            continue
        mode = (c.load_config(folder).get("mode") or "single")
        for label, _, files in streams:
            w = sum(c.count_words(c.read(f)) for f in files)
            print("%-26s %-6s %-34s %5d %9s"
                  % (d[:26], mode, label[:34], len(files), "{:,}".format(w)))
            tot[0] += 1; tot[1] += len(files); tot[2] += w
    print("\n%d projects, %d context files, %s words"
          % (tot[0], tot[1], "{:,}".format(tot[2])))
    s = json.load(open(os.path.join(os.path.expanduser("~"), ".claude",
                                    "settings.json"), encoding="utf-8"))
    live = any("context-system" in json.dumps(g)
               for g in (s.get("hooks", {}).get("Stop") or []))
    print("automatic recording: %s" % ("ON" if live else "OFF"))


def cmd_mode(name, mode):
    folder = find_folder(name)
    if not folder:
        print("no such folder: %s" % name); return 1
    if mode not in ("single", "multi"):
        print("mode must be single or multi"); return 1
    cfg = c.load_config(folder)
    cfg["mode"] = mode
    cfg["mode_locked"] = True
    c.save_config(folder, cfg)
    print("%s -> %s. Now run:  python ctx.py rebuild \"%s\""
          % (folder, mode, os.path.basename(folder)))


def cmd_rename(name, slug, label):
    folder = find_folder(name)
    if not folder:
        print("no such folder: %s" % name); return 1
    cfg = c.load_config(folder)
    if (cfg.get("mode") or "single") == "single":
        cfg["project"] = label
    else:
        cfg.setdefault("labels", {})[slug] = label
    c.save_config(folder, cfg)
    c.rebuild_index(folder)
    print("renamed in %s: %s -> %s" % (folder, slug, label))


def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help", "help"):
        print(__doc__); return 0
    cmd = a[0]
    if cmd == "status":
        return cmd_status()
    if cmd == "check":
        return run("verify.py")
    if cmd == "memcheck":
        return run("memcheck.py")
    if cmd == "prompts":
        return run("make_prompts.py")
    if cmd == "audit":
        if "--rescan" in a or not os.path.isfile(os.path.join(HERE, "audit.json")):
            if run("audit.py"):
                return 1
        return run("audit_report.py")
    if cmd == "rebuild":
        return run("backfill.py", *a[1:])
    if cmd == "mode" and len(a) == 3:
        return cmd_mode(a[1], a[2])
    if cmd == "rename" and len(a) == 4:
        return cmd_rename(a[1], a[2], a[3])
    if cmd == "on":
        return run("install_hooks.py")
    if cmd == "off":
        return run("install_hooks.py", "--remove")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main() or 0)
