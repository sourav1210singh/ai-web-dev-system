# -*- coding: utf-8 -*-
"""Does the fix job runner hold state correctly and diff honestly?

The two network checks are stubbed, so this tests the state machine and the
before/after comparison rather than the internet.
"""
import importlib.util, io, os, shutil, sys, tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def load():
    spec = importlib.util.spec_from_file_location(
        "jobmod", os.path.join(HERE, "job.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(fn, a):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = fn(a)
    return rc, buf.getvalue()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    job = load()
    tmp = tempfile.mkdtemp(prefix="jobtest_")

    # --- the pure readers -------------------------------------------------
    ok("spots a missing launch file",
       job.launch_problems("  llms       MISSING (404)") == ["llms       MISSING (404)"])
    ok("spots an og:image on the wrong domain",
       len(job.launch_problems("  og_image   https://x.lovable.app/a.jpg  <-- WRONG DOMAIN")) == 1)
    ok("spots a zero-byte favicon",
       len(job.launch_problems("  favicon    0 bytes, image/x-icon, md5 d41d")) == 1)
    ok("a clean line is not a problem",
       job.launch_problems("  sitemap    25 URLs") == [])
    ok("keeps only blocker and major responsive findings",
       job.rqa_problems([{"sev": "BLOCKER", "width": 390, "kind": "overflow",
                          "msg": "sideways scroll"},
                         {"sev": "MINOR", "width": 390, "msg": "nit"}]) ==
       ["BLOCKER overflow: sideways scroll  [390px]"])
    ok("reports a responsive run that could not happen",
       job.rqa_problems({"error": "rqa.js not found"})[0].startswith("responsive QA:"))

    # the shape rqa.js actually writes: findings nested inside viewports
    real = {"counts": {"BLOCKER": 0, "MAJOR": 2, "MINOR": 1},
            "viewports": [
                {"width": 390, "findings": [
                    {"sev": "MAJOR", "kind": "tap-target",
                     "msg": "Tap target is 40x40px, below the 44x44 minimum."},
                    {"sev": "MINOR", "kind": "nit", "msg": "ignore me"}]},
                {"width": 768, "findings": [
                    {"sev": "MAJOR", "kind": "tap-target",
                     "msg": "Tap target is 40x40px, below the 44x44 minimum."}]}]}
    got = job.rqa_problems(real)
    ok("reads findings nested inside viewports", len(got) == 1, got)
    ok("the same fault at two widths is reported once, with both widths",
       got and "390px, 768px" in got[0], got[0] if got else "")
    ok("a findings file with nothing in it is not called clean",
       job.rqa_problems({"url": "x"})[0].startswith("responsive QA:"))

    pos, flags = job.parse_args(["abc", "--domain", "x.com", "--route", "lovable"])
    ok("parses positional and flag arguments",
       pos == ["abc"] and flags["domain"] == "x.com" and flags["route"] == "lovable")

    # --- the state machine, with the network stubbed ----------------------
    state = {"launch": "  favicon    0 bytes\n  llms       MISSING (404)",
             "rqa": [{"sev": "BLOCKER", "width": 390, "msg": "sideways scroll"}]}
    job.run_check = lambda d: state["launch"]
    job.run_rqa = lambda u, o: state["rqa"]

    rc, out = run(job.cmd_new, {"name": "Demo Fix", "domain": "example.test",
                                "dir": tmp, "route": "lovable"})
    jid = None
    for line in out.splitlines():
        if line.startswith("job ") and " opened" in line:
            jid = line.split()[1]
    ok("new opens a job and sets the route", rc == 0 and jid, out.strip()[:60])
    j, _p = job.find(jid, tmp)
    ok("a route given up front skips to read", j["stage"] == "read")

    rc, out = run(job.cmd_diagnose, {"id": jid, "dir": tmp})
    j, _p = job.find(jid, tmp)
    ok("diagnose records both problems", rc == 0 and
       len(j["snapshots"]["before"]["launch"]) == 2 and
       len(j["snapshots"]["before"]["responsive"]) == 1)
    ok("diagnose moves the job to apply", j["stage"] == "apply")
    ok("the digest tells you to read the screenshots",
       "Read the screenshots" in out)

    rc, out = run(job.cmd_gate, {"id": jid, "dir": tmp,
                                 "awaiting": "user-paste",
                                 "note": "prompt-demo.md"})
    j, _p = job.find(jid, tmp)
    ok("the gate records what it is waiting for",
       j["awaiting"] == "user-paste" and "prompt-demo.md" in out)

    rc, out = run(job.cmd_status, {"id": jid, "dir": tmp})
    ok("status shows a waiting job as waiting", "WAITING: user-paste" in out)

    # the user does their part, and the site genuinely improves
    state["launch"] = "  favicon    5430 bytes\n  llms       ok, 31 lines"
    state["rqa"] = []
    rc, out = run(job.cmd_resume, {"id": jid, "dir": tmp})
    j, _p = job.find(jid, tmp)
    ok("resume clears the gate and moves to verify",
       j["awaiting"] is None and j["stage"] == "verify")

    rc, out = run(job.cmd_verify, {"id": jid, "dir": tmp})
    ok("verify exits 0 when nothing regressed", rc == 0, "rc=%d" % rc)
    ok("verify lists what was fixed", out.count("FIXED") == 3, out.count("FIXED"))
    ok("verify reports no new problems", "NEW " not in out)

    # --- a run where the change breaks something new ----------------------
    state["launch"] = "  favicon    0 bytes"
    state["rqa"] = []
    rc2, out2 = run(job.cmd_new, {"name": "Regress", "domain": "example.test",
                                  "dir": tmp, "route": "direct"})
    jid2 = [l.split()[1] for l in out2.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    run(job.cmd_diagnose, {"id": jid2, "dir": tmp})
    state["launch"] = "  favicon    0 bytes\n  og_image   https://x.lovable.app/a.jpg  <-- WRONG DOMAIN"
    rc, out = run(job.cmd_verify, {"id": jid2, "dir": tmp})
    ok("verify exits 1 when something new breaks", rc == 1, "rc=%d" % rc)
    ok("the new problem is named", "NEW " in out and "WRONG DOMAIN" in out)
    ok("it says not to close while something is worse",
       "before closing" in out)

    rc, out = run(job.cmd_close, {"id": jid, "dir": tmp, "summary": "done"})
    j, _p = job.find(jid, tmp)
    ok("close marks the job closed", rc == 0 and j["stage"] == "closed")
    ok("close points at the client log", "CLIENT-LOG" in out)

    rc, out = run(job.cmd_status, {"dir": tmp})
    ok("list shows both jobs", jid in out and jid2 in out)

    rc, out = run(job.cmd_diagnose, {"id": "no-such-job", "dir": tmp})
    ok("an unknown job id is refused, not invented", rc == 2)

    ok("the job file lives in the project, not the temp folder",
       os.path.isfile(os.path.join(tmp, ".claude-context", "jobs",
                                   jid + ".json")))

    shutil.rmtree(tmp, ignore_errors=True)
    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
