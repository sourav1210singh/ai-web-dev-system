# -*- coding: utf-8 -*-
"""Run every open watch job, and leave a record that says when it last ran.

    python watchrun.py [--dry-run] [--root <workspace>] [--schedule]

Nothing in this system ran by itself. `fix-job watch` existed and needed a
person to remember it every week, which means a form that quietly disappears is
found when the client asks where the leads went.

This is the half that belongs in the repo: find the open watch jobs, run them,
collect what changed into one summary a person reads, and record the run. The
other half - *when* - belongs to the operating system, and `--schedule` prints
the command to register it.

**It does not create the scheduled task itself.** Registering one changes the
machine's configuration, which is the user's to do, not a script's. What this
does do is *read* whether the task exists, so `--status` can say plainly that
the weekly run was never set up, rather than leaving everyone to assume it was.

The staleness marker matters as much as the run. A schedule that silently
stopped looks exactly like a site with no problems.
"""
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
JOB = os.path.join(HERE, "job.py")
TASK_NAME = "AI-dev-system weekly watch"
# A run older than this means the schedule is not working, whatever it claims.
STALE_DAYS = 10


def workspace(root=None):
    if root:
        return os.path.abspath(root)
    # skills/fix-job -> skills -> .ai-system -> the workspace
    return os.path.dirname(os.path.dirname(os.path.dirname(HERE)))


def state_dir(root):
    return os.path.join(root, ".context-system", "watch")


def open_watch_jobs(root):
    """Every open watch job in every project under the workspace."""
    found = []
    for name in sorted(os.listdir(root)):
        proj = os.path.join(root, name)
        jobs = os.path.join(proj, ".claude-context", "jobs")
        if not os.path.isdir(jobs):
            continue
        for f in sorted(os.listdir(jobs)):
            if not f.endswith(".json"):
                continue
            try:
                j = json.loads(io.open(os.path.join(jobs, f),
                                       encoding="utf-8").read())
            except Exception:
                continue
            if j.get("type") != "watch" or j.get("stage") == "closed":
                continue
            found.append({"id": j.get("id"), "project": proj,
                          "name": j.get("name") or "", "domain": j.get("domain")})
    return found


def run_one(job):
    """One watch run. Returns (changed, rc, output)."""
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", JOB, "watch",
                            job["id"], "--dir", job["project"]],
                           capture_output=True, text=True, timeout=3600)
    except Exception as e:
        return True, 2, "could not run: %s" % e
    out = (p.stdout or "") + (p.stderr or "")
    # job.py watch prints NEW / GONE lines only when something moved.
    changed = bool(re.search(r"^\s*(NEW|GONE)\s", out, re.M))
    return changed, p.returncode, out


def summarise(results, root):
    L = ["# Weekly watch - %s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    moved = [r for r in results if r["changed"]]
    if not results:
        L.append("No open watch jobs. Nothing is being watched, which is a "
                 "finding in itself if any of these sites are live.")
    else:
        L.append("%d site(s) checked, %d with something different."
                 % (len(results), len(moved)))
        L.append("")
    for r in results:
        L.append("## %s%s" % (r["name"] or r["id"],
                              "" if r["changed"] else " - no change"))
        if r["domain"]:
            L.append(r["domain"])
        if r["changed"]:
            lines = [l for l in r["output"].splitlines()
                     if re.match(r"^\s*(NEW|GONE)\s", l)]
            L += ["  " + l.strip() for l in lines[:25]]
            if r["rc"] == 2:
                L.append("  the run itself failed: " + r["output"].strip()[:200])
        L.append("")
    L.append('"Nothing has changed since the last run" is a real answer and '
             "worth sending to the client as plainly as a list of problems.")
    return "\n".join(L)


def task_registered():
    """Read-only: is a weekly task actually registered on this machine?"""
    try:
        p = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME],
                           capture_output=True, text=True, timeout=30)
        return p.returncode == 0
    except Exception:
        return None          # cannot tell, which is not the same as "no"


def schedule_command(root):
    return ('schtasks /create /tn "%s" /tr "\\"%s\\" -X utf8 \\"%s\\" --root '
            '\\"%s\\"" /sc weekly /d MON /st 07:00 /f'
            % (TASK_NAME, sys.executable, os.path.join(HERE, "watchrun.py"), root))


def last_run(root):
    p = os.path.join(state_dir(root), "last-run.json")
    if not os.path.isfile(p):
        return None
    try:
        return json.loads(io.open(p, encoding="utf-8").read())
    except Exception:
        return None


def staleness(root, today=None):
    """What to say about the schedule, as a (severity, message) pair."""
    today = today or datetime.now()
    reg = task_registered()
    lr = last_run(root)
    if not lr:
        return ("MAJOR", "The weekly watch has never run."
                + ("" if reg else " No scheduled task is registered for it."))
    try:
        when = datetime.strptime(lr["taken"][:16], "%Y-%m-%d %H:%M")
    except Exception:
        return ("MAJOR", "The last-run record is unreadable.")
    days = (today - when).days
    if days > STALE_DAYS:
        return ("MAJOR", "The weekly watch last ran %d days ago (%s). A "
                "schedule that stopped looks exactly like a site with no "
                "problems." % (days, lr["taken"]))
    return ("OK", "Last ran %s, %d site(s) checked."
            % (lr["taken"], lr.get("sites", 0)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    root = None
    if "--root" in args:
        i = args.index("--root")
        root = args[i + 1] if i + 1 < len(args) else None
    root = workspace(root)

    if "--schedule" in args:
        print("Run this yourself to register the weekly run. It changes the\n"
              "machine's configuration, so this script will not do it for you:\n")
        print("  " + schedule_command(root))
        print("\nThen check it with:  python watchrun.py --status")
        return 0

    if "--status" in args:
        sev, msg = staleness(root)
        reg = task_registered()
        print("scheduled task: %s" % ("registered" if reg else
                                      "NOT registered" if reg is False
                                      else "could not be checked"))
        print("%-8s %s" % (sev, msg))
        for j in open_watch_jobs(root):
            print("  watching %-28s %s" % (j["name"][:28], j["domain"] or ""))
        return 0 if sev == "OK" else 1

    jobs = open_watch_jobs(root)
    if "--dry-run" in args:
        print("%d open watch job(s) under %s" % (len(jobs), root))
        for j in jobs:
            print("  %-22s %-28s %s" % (j["id"], j["name"][:28], j["domain"] or ""))
        return 0

    results = []
    for j in jobs:
        changed, rc, out = run_one(j)
        results.append(dict(j, changed=changed, rc=rc, output=out))

    os.makedirs(state_dir(root), exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    text = summarise(results, root)
    io.open(os.path.join(state_dir(root),
                         datetime.now().strftime("%Y-%m-%d") + "-watch.md"),
            "w", encoding="utf-8", newline="\n").write(text + "\n")
    io.open(os.path.join(state_dir(root), "last-run.json"), "w",
            encoding="utf-8", newline="\n").write(json.dumps({
                "taken": stamp, "sites": len(results),
                "changed": sum(1 for r in results if r["changed"]),
                "failed": sum(1 for r in results if r["rc"] == 2),
            }, indent=2) + "\n")
    print(text)
    # Non-zero when something moved, so a scheduler's own failure mail is the
    # signal rather than something nobody reads.
    return 1 if any(r["changed"] for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
