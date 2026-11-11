# -*- coding: utf-8 -*-
"""Does the weekly runner find the right jobs, and admit when it never ran?

The staleness check is the point of this file. A schedule that silently stopped
looks exactly like a set of sites with no problems, so "never ran" and "last ran
three weeks ago" both have to be loud.

    python watchtest.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import watchrun as W  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:120] + "]") if extra else ""))


def mkjob(root, project, jid, jtype="watch", stage="diagnose", domain="x.test"):
    d = os.path.join(root, project, ".claude-context", "jobs")
    os.makedirs(d, exist_ok=True)
    io.open(os.path.join(d, jid + ".json"), "w", encoding="utf-8").write(
        json.dumps({"id": jid, "type": jtype, "stage": stage,
                    "name": project + " watch", "domain": domain}))


tmp = tempfile.mkdtemp(prefix="watchtest-")
try:
    mkjob(tmp, "Client A", "a-watch-001")
    mkjob(tmp, "Client B", "b-watch-001")
    mkjob(tmp, "Client B", "b-fix-002", jtype="fix")
    mkjob(tmp, "Client C", "c-watch-003", stage="closed")
    os.makedirs(os.path.join(tmp, "Not A Project"), exist_ok=True)

    jobs = W.open_watch_jobs(tmp)
    ids = sorted(j["id"] for j in jobs)
    ok("every open watch job is found across projects",
       ids == ["a-watch-001", "b-watch-001"], ids)
    ok("a fix job in the same project is not picked up",
       "b-fix-002" not in ids, "only watch jobs run weekly")
    ok("a closed watch job is not run again",
       "c-watch-003" not in ids)
    ok("a folder with no jobs directory is skipped quietly",
       len(jobs) == 2)
    ok("each job carries the project folder it belongs to",
       all(os.path.isdir(j["project"]) for j in jobs))

    # ----------------------------------------------------- staleness
    sev, msg = W.staleness(tmp)
    ok("a workspace that has never run is reported as a major finding",
       sev == "MAJOR" and "never run" in msg, msg)

    os.makedirs(W.state_dir(tmp), exist_ok=True)
    now = datetime(2026, 11, 10, 7, 0)

    def write_last(when, sites=2):
        io.open(os.path.join(W.state_dir(tmp), "last-run.json"), "w",
                encoding="utf-8").write(json.dumps({
                    "taken": when.strftime("%Y-%m-%d %H:%M"), "sites": sites,
                    "changed": 0, "failed": 0}))

    write_last(now - timedelta(days=2))
    sev, msg = W.staleness(tmp, today=now)
    ok("a run from two days ago is fine", sev == "OK", msg)
    ok("and it says how many sites were checked", "2 site(s)" in msg, msg)

    write_last(now - timedelta(days=21))
    sev, msg = W.staleness(tmp, today=now)
    ok("a run from three weeks ago is a major finding",
       sev == "MAJOR" and "21 days ago" in msg, msg)
    ok("and it says why that matters",
       "looks exactly like a site with no problems" in msg,
       "silence is indistinguishable from health")

    write_last(now - timedelta(days=W.STALE_DAYS - 1))
    ok("just inside the window is still fine",
       W.staleness(tmp, today=now)[0] == "OK")
    write_last(now - timedelta(days=W.STALE_DAYS + 1))
    ok("just outside it is not",
       W.staleness(tmp, today=now)[0] == "MAJOR")

    io.open(os.path.join(W.state_dir(tmp), "last-run.json"), "w",
            encoding="utf-8").write("{not json")
    ok("an unreadable last-run record is reported, not ignored",
       W.staleness(tmp, today=now)[0] == "MAJOR")

    # A schedule with nothing in it. Registering the task and running it once
    # turned "never run" into OK while zero sites were being watched, which
    # is the same silence this file exists to break, one step further on.
    empty = tempfile.mkdtemp(prefix="watchtest-empty-")
    try:
        os.makedirs(W.state_dir(empty), exist_ok=True)
        io.open(os.path.join(W.state_dir(empty), "last-run.json"), "w",
                encoding="utf-8").write(json.dumps(
                    {"taken": (now - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"),
                     "sites": 0, "changed": 0, "failed": 0}))
        ok("no open watch jobs is not OK, however recently it ran",
           W.staleness(empty, today=now)[0] == "MAJOR",
           W.staleness(empty, today=now)[1])
        ok("and it says plainly that nothing is being watched",
           "watched nothing" in W.staleness(empty, today=now)[1],
           W.staleness(empty, today=now)[1])
        mkjob(empty, "Client D", "d-watch-001")
        ok("one open job and a recent run is OK again",
           W.staleness(empty, today=now)[0] == "OK",
           W.staleness(empty, today=now)[1])
    finally:
        shutil.rmtree(empty, ignore_errors=True)

    # ------------------------------------------------------- the summary
    res = [{"id": "a", "name": "Client A watch", "domain": "a.test",
            "changed": True, "rc": 1,
            "output": "  NEW    BLOCKER: /.env is publicly readable\n"
                      "  GONE   tags: 1 hit(s) to G-ABC123\n"},
           {"id": "b", "name": "Client B watch", "domain": "b.test",
            "changed": False, "rc": 0, "output": "nothing changed\n"}]
    text = W.summarise(res, tmp)
    ok("the summary counts the sites and the ones that moved",
       "2 site(s) checked, 1 with something different" in text, text[:80])
    ok("it carries the NEW and GONE lines for a site that moved",
       "/.env is publicly readable" in text and "G-ABC123" in text)
    ok("a site with no change is marked as such",
       "Client B watch - no change" in text)
    ok("it keeps the line about no change being a real answer",
       "worth sending to the client" in text)

    empty = W.summarise([], tmp)
    ok("no watch jobs at all is itself called out",
       "Nothing is being watched" in empty,
       "a live site nobody watches is a finding")

    failed = W.summarise([{"id": "a", "name": "A", "domain": "a.test",
                           "changed": True, "rc": 2,
                           "output": "could not run: boom"}], tmp)
    ok("a run that failed outright says so rather than reading as a change",
       "the run itself failed" in failed)

    # --------------------------------------------------- the schedule
    cmd = W.schedule_command(tmp)
    ok("the schedule command names the task and runs weekly",
       W.TASK_NAME in cmd and "/sc weekly" in cmd, cmd[:90])
    ok("it passes the workspace root through", tmp in cmd)
    ok("it uses the interpreter that is actually running",
       sys.executable in cmd,
       "not a remembered path to some other python")
    ok("checking for the task is read-only and returns a verdict",
       W.task_registered() in (True, False, None))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
