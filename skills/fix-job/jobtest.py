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
             "rqa": [{"sev": "BLOCKER", "width": 390, "msg": "sideways scroll"}],
             # golive and intake both run the security pass now, so it is
             # stubbed here or the suite goes out to the network.
             "security": {"findings": [], "thirdParty": [], "cookies": 0,
                          "scriptsScanned": 3},
             # golive runs the rollback check too, stubbed here so the suite
             # does not go near the network or a real plan.
             "rollback": {"findings": [], "plan": {"verified_on": "2026-11-10"}},
             "seo": {"findings": [], "counts": {"pages read": 4,
                                                "internal links checked": 20,
                                                "internal links broken": 0}}}
    job.run_check = lambda d: state["launch"]
    job.run_rqa = lambda u, o: state["rqa"]
    job.run_security = lambda u, o: state["security"]
    job.run_rollback = lambda p: state["rollback"]
    job.run_seo = lambda u, o: state["seo"]

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

    # --- intake: reads, never changes ------------------------------------
    # the shape recon.py actually writes: a markdown report, read from a file
    REPORT = ("# Site recon - example.test\n\n"
              "Checked 2026-10-21T10:00.\n\n"
              "## Domain\n\n"
              "- **Registrar:** Example Registrar Inc\n"
              "- RDAP lookup failed: HTTP 400\n\n"
              "## Hosting\n\n"
              "- **Server header:** cloudflare\n"
              "- **TLS:** Example CA, expires Jan 9 2027\n\n"
              "## Site\n\n"
              "- **Platform / CMS:** ['WordPress']\n"
              "- **Title:** Example Title\n"
              "some noise line that is not a fact\n")
    job.run_recon = lambda d, out: REPORT

    facts = job.recon_facts(REPORT)
    ok("recon parses the real report format, not progress output",
       any(f.startswith("Domain / Registrar:") for f in facts), facts[:1])
    ok("recon keeps the section a fact came from",
       any(f.startswith("Hosting / TLS:") for f in facts))
    ok("recon keeps a lookup failure, because someone has to act on it",
       any("RDAP lookup failed" in f for f in facts))
    ok("recon drops lines that are not facts",
       not any("some noise line" in f for f in facts))
    ok("a short error string survives as its own line",
       job.recon_facts("recon.py not found") == ["recon.py not found"])
    state["launch"] = "  llms       MISSING (404)"
    state["rqa"] = []
    rc, out = run(job.cmd_new, {"name": "New Client", "domain": "example.test",
                                "dir": tmp, "type": "intake"})
    jid3 = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    j, _p = job.find(jid3, tmp)
    ok("intake starts at recon, not route", j["stage"] == "recon")
    ok("intake says it changes nothing", "changes nothing" in out)

    rc, out = run(job.cmd_diagnose, {"id": jid3, "dir": tmp})
    j, _p = job.find(jid3, tmp)
    ok("intake goes to report, never to apply", j["stage"] == "report")
    ok("intake has no gate in its next steps", "gate" not in out)
    ok("intake reports what the domain says",
       "Domain / Registrar: Example Registrar Inc" in out and
       "Site / Platform / CMS" in out)
    ok("the digest drops lines that are not facts",
       "some noise line" not in out)
    ok("intake does not run a parity check",
       "parity" not in (j["snapshots"]["before"]["ran"]))

    rc, out = run(job.cmd_close, {"id": jid3, "dir": tmp, "summary": "noted"})
    ok("an intake job closes without a verify step", rc == 0)

    # --- golive: refuses to close over a blocker --------------------------
    state["launch"] = "  favicon    MISSING (404)"
    state["rqa"] = [{"sev": "BLOCKER", "width": 390, "kind": "overflow",
                     "msg": "sideways scroll"}]
    rc, out = run(job.cmd_new, {"name": "Launch", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jid4 = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    rc, out = run(job.cmd_diagnose, {"id": jid4, "dir": tmp})
    ok("golive counts what is blocking the launch", "blocker(s) standing" in out)

    rc, out = run(job.cmd_close, {"id": jid4, "dir": tmp, "summary": "ship it"})
    ok("golive refuses to close over a standing blocker", rc == 1, "rc=%d" % rc)
    ok("the refusal names the blockers", "favicon" in out or "sideways" in out)
    j, _p = job.find(jid4, tmp)
    ok("a refused close leaves the job open", j["stage"] != "closed")

    rc, out = run(job.cmd_close, {"id": jid4, "dir": tmp, "summary": "ship it",
                                  "force": "true"})
    j, _p = job.find(jid4, tmp)
    ok("--force closes it but records that it was a decision",
       rc == 0 and j["stage"] == "closed" and
       any("CLOSED OVER STANDING BLOCKERS" in h for h in j["history"]))

    # a clean golive closes normally
    state["launch"] = "  favicon    5430 bytes"
    state["rqa"] = []
    rc, out = run(job.cmd_new, {"name": "Clean launch", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jid5 = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    run(job.cmd_diagnose, {"id": jid5, "dir": tmp})
    rc, out = run(job.cmd_close, {"id": jid5, "dir": tmp, "summary": "live"})
    ok("a clean golive closes without force", rc == 0, "rc=%d" % rc)

    # --- golive and a key in the bundle ----------------------------------
    # The whole reason the security pass is one of the launch gate's checks.
    state["launch"] = "  favicon    5430 bytes"
    state["rqa"] = []
    state["security"] = {"thirdParty": ["cdn.example"], "cookies": 2,
                         "scriptsScanned": 4, "findings": [
        {"sev": "BLOCKER", "title": "Supabase service_role key - bypasses row level security"},
        {"sev": "MAJOR", "title": "No Content-Security-Policy"}]}
    rc, out = run(job.cmd_new, {"name": "Leaky launch", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jid6 = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    rc, out = run(job.cmd_diagnose, {"id": jid6, "dir": tmp})
    ok("security is one of the launch gate's checks",
       "security" in job.JOB_TYPES["golive"]["checks"])
    ok("the digest has a security section", "**Security**" in out)
    rc, out = run(job.cmd_close, {"id": jid6, "dir": tmp, "summary": "ship it"})
    ok("a key in the bundle stops the launch", rc == 1, "rc=%d" % rc)
    ok("the refusal names the key", "service_role" in out)

    # A missing CSP is a real finding and not a reason to refuse a launch.
    state["security"] = {"thirdParty": [], "cookies": 0, "scriptsScanned": 1,
                         "findings": [{"sev": "MAJOR", "title": "No Content-Security-Policy"},
                                      {"sev": "MINOR", "title": "No Referrer-Policy"}]}
    rc, out = run(job.cmd_new, {"name": "No CSP", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jid7 = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    run(job.cmd_diagnose, {"id": jid7, "dir": tmp})
    rc, out = run(job.cmd_close, {"id": jid7, "dir": tmp, "summary": "live"})
    ok("a major security finding does not refuse the launch on its own",
       rc == 0, "rc=%d - a gate that blocks the normal web gets forced" % rc)
    j, _p = job.find(jid7, tmp)
    ok("but it is still recorded against the job",
       any("Content-Security-Policy" in l
           for l in j["snapshots"]["before"]["security"]))
    ok("the counted surface line never starts with BLOCKER",
       not any(l.startswith("BLOCKER") and "surface:" in l
               for l in j["snapshots"]["before"]["security"]),
       "blockers() keys off that prefix")

    # --- golive and the way back ------------------------------------------
    # A launch with no way back is the one that cannot be undone at 7pm on a
    # Friday, which is the whole reason this is a gate and not a reminder.
    state["launch"] = "  favicon    5430 bytes"
    state["rqa"] = []
    state["security"] = {"findings": [], "thirdParty": [], "cookies": 0,
                         "scriptsScanned": 1}
    state["rollback"] = {"findings": [
        {"sev": "BLOCKER", "title": "The named backup is not there"},
        {"sev": "MAJOR", "title": "No TTL is recorded"}], "plan": {}}
    rc, out = run(job.cmd_new, {"name": "No way back", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jidr = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    rc, out = run(job.cmd_diagnose, {"id": jidr, "dir": tmp})
    ok("rollback is one of the launch gate's checks",
       "rollback" in job.JOB_TYPES["golive"]["checks"])
    ok("the digest has a rollback section", "**Rollback plan**" in out)
    rc, out = run(job.cmd_close, {"id": jidr, "dir": tmp, "summary": "ship it"})
    ok("a backup that is not there stops the launch", rc == 1, "rc=%d" % rc)
    ok("the refusal names what is missing", "backup is not there" in out)

    state["rollback"] = {"findings": [{"sev": "MAJOR", "title": "No TTL is recorded"}],
                         "plan": {"verified_on": "2026-11-10"}}
    rc, out = run(job.cmd_new, {"name": "Slow revert", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jids = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    run(job.cmd_diagnose, {"id": jids, "dir": tmp})
    rc, out = run(job.cmd_close, {"id": jids, "dir": tmp, "summary": "live"})
    ok("a slow revert is worth saying and does not refuse the launch", rc == 0,
       "rc=%d" % rc)

    state["rollback"] = {"findings": [], "plan": {"verified_on": "2026-11-10"}}
    rc, out = run(job.cmd_new, {"name": "Has a way back",
                                "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jidw = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    rc, out = run(job.cmd_diagnose, {"id": jidw, "dir": tmp})
    ok("a verified plan is reported as executable", "executable as written" in out)
    rc, out = run(job.cmd_close, {"id": jidw, "dir": tmp, "summary": "live"})
    ok("a launch with a verified way back closes", rc == 0, "rc=%d" % rc)

    # Closing is the only moment anyone is prompted to compare the quote with
    # what it took, so a project that has an estimate on file gets told.
    state["security"] = {"findings": [], "thirdParty": [], "cookies": 0,
                         "scriptsScanned": 1}
    io.open(os.path.join(tmp, ".claude-context", "estimate.json"), "w",
            encoding="utf-8").write('{"project": "x", "items": []}')
    rc, out = run(job.cmd_new, {"name": "Priced", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jid8 = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    run(job.cmd_diagnose, {"id": jid8, "dir": tmp})
    rc, out = run(job.cmd_close, {"id": jid8, "dir": tmp, "summary": "live"})
    ok("closing a project that has a recorded estimate points at the comparison",
       rc == 0 and "estimate.py" in out and "compare" in out,
       [l for l in out.splitlines() if "estimate" in l][:1])
    os.remove(os.path.join(tmp, ".claude-context", "estimate.json"))
    rc, out = run(job.cmd_new, {"name": "Unpriced", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jid9 = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    run(job.cmd_diagnose, {"id": jid9, "dir": tmp})
    rc, out = run(job.cmd_close, {"id": jid9, "dir": tmp, "summary": "live"})
    ok("a project with no estimate on file is not nagged about one",
       "estimate.py" not in out)

    # --- golive and SEO ---------------------------------------------------
    # The skill demanded these counts for months and shipped no way to produce
    # them, so they were eyeballed. Now they gate.
    state["rollback"] = {"findings": [], "plan": {"verified_on": "2026-11-10"}}
    state["seo"] = {"counts": {"pages read": 4, "internal links checked": 20,
                               "internal links broken": 3},
                    "findings": [
        {"sev": "BLOCKER", "title": "3 internal link(s) do not resolve"},
        {"sev": "MAJOR", "title": "Meta description is Missing"}]}
    rc, out = run(job.cmd_new, {"name": "Dead links", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jidq = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    rc, out = run(job.cmd_diagnose, {"id": jidq, "dir": tmp})
    ok("seo is one of the launch gate's checks",
       "seo" in job.JOB_TYPES["golive"]["checks"])
    ok("the digest has an SEO section", "**SEO**" in out)
    rc, out = run(job.cmd_close, {"id": jidq, "dir": tmp, "summary": "ship it"})
    ok("a broken internal link stops the launch", rc == 1, "rc=%d" % rc)
    ok("the refusal names it", "do not resolve" in out)

    state["seo"] = {"counts": {"pages read": 4, "internal links checked": 20,
                               "internal links broken": 0},
                    "findings": [{"sev": "MAJOR", "title": "Meta description is Missing"}]}
    rc, out = run(job.cmd_new, {"name": "Thin meta", "domain": "example.test",
                                "dir": tmp, "type": "golive"})
    jidt = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    run(job.cmd_diagnose, {"id": jidt, "dir": tmp})
    rc, out = run(job.cmd_close, {"id": jidt, "dir": tmp, "summary": "live"})
    ok("a missing meta description is reported and does not stop the launch",
       rc == 0, "rc=%d" % rc)
    j, _p = job.find(jidt, tmp)
    ok("the counts are recorded against the job",
       any("20 link(s) checked" in l for l in j["snapshots"]["before"]["seo"]),
       j["snapshots"]["before"]["seo"])
    ok("seo is one of the watch checks",
       "seo" in job.JOB_TYPES["watch"]["checks"]
       and "seo" in [k for k, _ in job.WATCH_KEYS])

    # --- drop: a diagnosis, not a fix -------------------------------------
    state["launch"] = "  favicon    5430 bytes"
    state["rqa"] = []
    state["security"] = {"findings": [], "thirdParty": [], "cookies": 0,
                         "scriptsScanned": 1}
    state["seo"] = {"counts": {"pages read": 12, "internal links checked": 40,
                               "internal links broken": 7},
                    "findings": [
        {"sev": "MAJOR", "title": "An invalid URL returns 200, not 404"},
        {"sev": "BLOCKER", "title": "7 internal link(s) do not resolve"}]}
    rc, out = run(job.cmd_new, {"name": "Traffic down", "domain": "example.test",
                                "dir": tmp, "type": "drop"})
    jidd = [l.split()[1] for l in out.splitlines()
            if l.startswith("job ") and " opened" in l][0]
    rc, out = run(job.cmd_diagnose, {"id": jidd, "dir": tmp})
    ok("drop runs the seo and security passes",
       "seo" in job.JOB_TYPES["drop"]["checks"]
       and "security" in job.JOB_TYPES["drop"]["checks"])
    ok("drop also runs recon, because hosting and DNS moves cause drops",
       "recon" in job.JOB_TYPES["drop"]["checks"])
    ok("drop does not run the heavy page measurements",
       "perf" not in job.JOB_TYPES["drop"]["checks"]
       and "a11y" not in job.JOB_TYPES["drop"]["checks"],
       "vitals are not a usual cause of a ranking collapse")
    ok("the soft 404 shows in the drop digest", "returns 200, not 404" in out)
    rc, out = run(job.cmd_close, {"id": jidd, "dir": tmp, "summary": "diagnosed"})
    ok("a drop job closes without a gate, because it changes nothing",
       rc == 0, "rc=%d" % rc)
    ok("drop has no apply stage",
       "apply" not in job.JOB_TYPES["drop"]["stages"])
    j, _p = job.find(jidd, tmp)
    ok("the findings are recorded against the job",
       any("do not resolve" in l for l in j["snapshots"]["before"]["seo"]))

    rc, out = run(job.cmd_new, {"name": "Nope", "domain": "example.test",
                                "dir": tmp, "type": "nonsense"})
    ok("an unknown job type is refused", rc == 2)

    ok("the job file lives in the project, not the temp folder",
       os.path.isfile(os.path.join(tmp, ".claude-context", "jobs",
                                   jid + ".json")))

    shutil.rmtree(tmp, ignore_errors=True)

    # --- watch: a live site, and only what changed ------------------------
    # A job that ends at handover is a job that finds out from the client.
    job.run_perf = lambda u, o: {
        "findings": [{"sev": "MAJOR", "title": "LCP is over the target in the lab"}],
        "totalBytes": 1024 * 900, "requests": 40}
    job.run_a11y = lambda u, o: {"rows": [{
        "route": "/", "width": 390,
        "violations": [{"id": "color-contrast", "impact": "serious", "nodes": 3}],
        "sr": {"notes": [], "forms": 1, "submits": 1, "mailto": 0, "tel": 1},
        "focus": {"invisible": []}}]}
    # Stubbed, or the suite goes out to the network. The counting is what is
    # being tested, not the browser.
    job.run_analytics = lambda u, o: {
        "findings": [],
        "hits": [{"kind": "hit", "tid": "G-ABC123", "event": "page_view"}]}
    job.run_security = lambda u, o: state["security"]
    state["security"] = {"findings": [], "thirdParty": ["cdn.example"],
                         "cookies": 2, "scriptsScanned": 4}

    rc, out = run(job.cmd_new, {"name": "Watch It", "domain": "example.test",
                                "dir": tmp, "type": "watch", "route": "lovable"})
    wid = None
    for line in out.splitlines():
        if line.startswith("job ") and " opened" in line:
            wid = line.split()[1]
    ok("a watch job opens", rc == 0 and wid, out.strip()[:60])

    rc, out = run(job.cmd_watch, {"id": wid, "dir": tmp})
    ok("the first run is a baseline, not a report of changes",
       rc == 0 and "baseline" in out, out.strip()[-70:])
    ok("the baseline shows what it measured",
       "Load" in out and "Accessibility" in out)
    ok("the page weight is recorded even when it is fine",
       "900 KB" in out, [l for l in out.splitlines() if "KB" in l][:1])
    ok("the forms are counted so a later run can miss them",
       "1 form(s)" in out, [l for l in out.splitlines() if "form(s)" in l][:1])

    rc, out = run(job.cmd_watch, {"id": wid, "dir": tmp})
    ok("a second run with nothing changed says exactly that",
       rc == 0 and "Nothing has changed" in out, out.strip()[:70])

    # the forms are replaced with links to an off-site page, which is how a
    # real site ran for two months with the endpoint and mailer both healthy
    job.run_a11y = lambda u, o: {"rows": [{
        "route": "/", "width": 390,
        "violations": [{"id": "color-contrast", "impact": "serious", "nodes": 3}],
        "sr": {"notes": [], "forms": 0, "submits": 0, "mailto": 0, "tel": 1},
        "focus": {"invisible": []}}]}
    rc, out = run(job.cmd_watch, {"id": wid, "dir": tmp})
    ok("a form disappearing is reported as new", rc == 1 and "NEW" in out,
       [l for l in out.splitlines() if "NEW" in l][:1])
    ok("and the line that went is shown too", "GONE" in out)
    ok("it says what to act on", "Act on these" in out)

    # a page that doubles in weight is the finding, and no threshold alone
    # catches it
    job.run_perf = lambda u, o: {
        "findings": [{"sev": "MAJOR", "title": "LCP is over the target in the lab"}],
        "totalBytes": 1024 * 1800, "requests": 62}
    rc, out = run(job.cmd_watch, {"id": wid, "dir": tmp})
    ok("a page that got much heavier shows up as a change",
       "1800 KB" in out and "900 KB" in out,
       [l for l in out.splitlines() if "KB" in l][:2])

    # a fault that is fixed should read as fixed, not vanish quietly
    job.run_perf = lambda u, o: {"findings": [], "totalBytes": 1024 * 1800,
                                 "requests": 62}
    rc, out = run(job.cmd_watch, {"id": wid, "dir": tmp})
    ok("a fault that is fixed is reported as gone",
       "GONE   MAJOR: LCP is over the target in the lab" in out,
       [l for l in out.splitlines() if "LCP" in l][:1])


    # A tag that quietly stops firing is exactly what a weekly run is for: the
    # page still loads, nothing looks wrong, and the client's reports go flat.
    job.run_analytics = lambda u, o: {
        "findings": [{"sev": "BLOCKER", "title": "GA4 is on the page and sent nothing"}],
        "hits": []}
    rc, out = run(job.cmd_watch, {"id": wid, "dir": tmp})
    ok("a tag that stopped firing is reported as new",
       rc == 1 and "sent nothing" in out,
       [l for l in out.splitlines() if "NEW" in l][:2])
    ok("the hit count that went is shown as well",
       "GONE   tags: 1 hit(s) to G-ABC123" in out,
       [l for l in out.splitlines() if "tags:" in l][:2])

    ok("analytics is one of the watch checks",
       "analytics" in job.JOB_TYPES["watch"]["checks"])

    # A deploy that ships a key, or loses a header, looks like nothing from
    # the outside: the page still loads and nothing is visibly broken.
    state["security"] = {"findings": [
        {"sev": "BLOCKER", "title": "/.env is publicly readable: environment file"}],
        "thirdParty": ["cdn.example", "tracker.example"], "cookies": 2,
        "scriptsScanned": 4}
    rc, out = run(job.cmd_watch, {"id": wid, "dir": tmp})
    ok("a newly readable .env is reported as new",
       "/.env is publicly readable" in out,
       [l for l in out.splitlines() if "NEW" in l][:2])
    ok("a third-party script origin appearing shows up in the diff",
       "2 third party script origin(s)" in out,
       [l for l in out.splitlines() if "surface:" in l][:2])
    ok("security is one of the watch checks",
       "security" in job.JOB_TYPES["watch"]["checks"])

    ok("watch has no apply stage, because it changes nothing",
       "apply" not in job.JOB_TYPES["watch"]["stages"])
    ok("watch has no gate", job.JOB_TYPES["watch"]["gate"] is False)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
