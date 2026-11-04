# -*- coding: utf-8 -*-
"""Is auto-memory actually landing inside the project folders?

Claude Code reads settings at session start, so `autoMemoryDirectory` only
takes effect from the next session. This compares the old default location
with the new in-project one and says which is being written to.
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctxlib as c

PROJ = os.path.join(os.path.expanduser("~"), ".claude", "projects")
ROOT = os.path.abspath(c.ROOT)
SKIP = {".context-system"}


def sanitise(name):
    return ("C--Claude-Code-" + name).replace(" ", "-")


def newest(d):
    best = 0
    if os.path.isdir(d):
        for f in os.listdir(d):
            p = os.path.join(d, f)
            if os.path.isfile(p):
                best = max(best, os.path.getmtime(p))
    return best


def ago(t):
    if not t:
        return "-"
    s = time.time() - t
    if s < 3600:
        return "%dm ago" % (s // 60)
    if s < 86400:
        return "%dh ago" % (s // 3600)
    return "%dd ago" % (s // 86400)


def main():
    rows, drifting = [], []
    for name in sorted(os.listdir(ROOT)):
        folder = os.path.join(ROOT, name)
        if (not os.path.isdir(folder) or name in SKIP
                or name.startswith("_")
                or not os.path.isdir(c.ctx_dir_for(folder))):
            continue
        old = os.path.join(PROJ, sanitise(name), "memory")
        new = os.path.join(c.ctx_dir_for(folder), "memory")
        to, tn = newest(old), newest(new)
        nold = len(os.listdir(old)) if os.path.isdir(old) else 0
        nnew = len(os.listdir(new)) if os.path.isdir(new) else 0
        if to > tn + 5:
            state = "OLD still being written"
            drifting.append(name)
        elif tn >= to and tn:
            state = "in project folder  OK"
        else:
            state = "no memory yet"
        rows.append((name, nold, nnew, ago(to), ago(tn), state))

    print("%-26s %5s %5s %-10s %-10s %s"
          % ("PROJECT", "OLD", "NEW", "OLD TOUCHED", "NEW TOUCHED", "STATE"))
    for r in rows:
        print("%-26s %5d %5d %-10s %-10s %s" % r)
    print()
    if drifting:
        print("%d project(s) are still writing memory to the old location:"
              % len(drifting))
        for d in drifting:
            print("  - " + d)
        print("\nIf this persists after you have worked a full session in that")
        print("folder, `autoMemoryDirectory` is not being honoured there - tell")
        print("Claude and the setting can be moved or reverted.")
    else:
        print("No project is writing memory to the old location.")
    print("\nReminder: a session started BEFORE the setting was added still")
    print("uses the old path. Judge this only on sessions started after.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
