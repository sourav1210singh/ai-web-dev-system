# -*- coding: utf-8 -*-
"""Does the rollback check refuse a plan that cannot be executed, and let a
real one through?

The second half matters as much as the first. A gate that can never be
satisfied gets forced open as a matter of routine, and then it is not stopping
anything - so there is a test here that a complete plan passes cleanly, and it
is the one to keep green.

    python rbtest.py
"""
import io
import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rollback as R  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:130] + "]") if extra else ""))


def sevs(findings):
    return [f[0] for f in findings]


def titled(findings, text):
    return [f for f in findings if text.lower() in f[1].lower()]


TODAY = date(2026, 11, 10)

# The real recon.json shape, taken from one on disk rather than remembered: a
# dict keyed "<TYPE> <name>", spf as {records,count}, dmarc as {record,policy}.
RECON = {
    "domain": "client.example",
    "dns": {
        "NS client.example": ["ns1.host.example", "ns2.host.example"],
        "A client.example": ["203.0.113.10"],
        "CNAME www.client.example": ["client.example"],
        "MX client.example": ["10 mail.protection.example"],
        "TXT client.example": ["v=spf1 include:spf.example -all"],
    },
    "spf": {"records": ["v=spf1 include:spf.example -all"], "count": 1},
    "dmarc": {"record": "v=DMARC1; p=none", "policy": "none"},
    "dkim_selectors_found": {"selector1": "v=DKIM1; k=rsa; p=MIGf..."},
    "ttl": {"A client.example": 300, "NS client.example": 86400,
            "MX client.example": 3600},
    "hosting": {"ips": ["203.0.113.10"], "reverse_dns": {},
                "behind_cloudflare": False},
    "http": {"apex": {"server": "nginx", "status": 200}},
}

tmp = tempfile.mkdtemp(prefix="rbtest-")
try:
    # ------------------------------------------------------- nothing at all
    f = R.check(None, today=TODAY)
    ok("no plan at all is a blocker",
       f and f[0][0] == "BLOCKER" and "no rollback plan" in f[0][1].lower())

    # ------------------------------------------------------------ building
    proj = os.path.join(tmp, "Client")
    os.makedirs(os.path.join(proj, ".claude-context", "qa", "run", "recon"))
    io.open(os.path.join(proj, ".claude-context", "qa", "run", "recon",
                         "recon.json"), "w", encoding="utf-8").write(
        json.dumps(RECON))
    plan, p = R.build(proj, "")
    ok("build finds the recon output on its own", "recon.json" in plan["from_recon"])
    ok("it takes the domain from the recon when none is given",
       plan["domain"] == "client.example")
    ok("the records that will change are recorded",
       "A client.example" in plan["dns_before"]["site"] and
       "CNAME www.client.example" in plan["dns_before"]["site"])
    ok("the nameservers are kept apart from the site records",
       "NS client.example" in plan["dns_before"]["nameservers"] and
       "NS client.example" not in plan["dns_before"]["site"])
    ok("the mail records are kept apart again",
       plan["dns_before"]["mail"]["mx"] and plan["dns_before"]["mail"]["spf"],
       "reverting the site does not revert mail")
    ok("DKIM selectors are listed",
       plan["dns_before"]["mail"]["dkim_selectors"] == ["selector1"])
    ok("the TTLs come across", plan["ttl_seconds"]["NS client.example"] == 86400)
    ok("the TTL note says it is a lower bound",
       "lower bound" in plan["ttl_note"])
    ok("the old host is recorded", plan["old_host"]["server"] == "nginx")
    ok("the fields only a human can answer are left empty, not guessed",
       all(not plan[k] for k in ("old_origin_url", "platform_rollback",
                                 "trigger", "who", "verified_on")))
    ok("a built plan is written where a person can open it",
       os.path.isfile(p) and p.endswith("rollback.json"))

    bare = os.path.join(tmp, "Bare")
    os.makedirs(bare)
    plan2, _ = R.build(bare, "other.example")
    ok("building with no recon leaves the records empty",
       plan2["dns_before"]["site"] == {} and plan2["from_recon"] == "")
    ok("and mail is unknown rather than absent",
       plan2["dns_before"]["mail"]["found_by_recon"] is None,
       "unknown has to stay a blocker")

    # --------------------------------------------------------------- mail
    ok("recorded MX records are not a finding",
       not titled(R.check_mail({"mx": {"MX x": ["10 m"]}, "spf": ["v=spf1"],
                                "dmarc": "v=DMARC1"}), "mail records"))
    ok("missing MX on a domain that has mail is a blocker",
       R.check_mail({"mx": {}, "found_by_recon": True})[0][0] == "BLOCKER")
    ok("missing MX when it was never recorded at all is a blocker",
       R.check_mail({"mx": {}})[0][0] == "BLOCKER", "unknown is not permission")
    m = R.check_mail({"mx": {}, "found_by_recon": False})
    ok("a domain with no mail is a minor, not a blocker",
       m and m[0][0] == "MINOR" and "no mail" in m[0][1].lower(),
       "a preview host would otherwise be blocked forever")
    ok("and that case says to confirm it rather than assuming",
       "confirm" in m[0][2].lower())
    ok("a missing SPF is major on its own",
       titled(R.check_mail({"mx": {"MX x": ["10 m"]}, "spf": []}), "SPF")[0][0]
       == "MAJOR")

    # ------------------------------------------------------------- backup
    ok("no backup named at all is a blocker",
       R.check_backup({})[0][0] == "BLOCKER")
    ok("and it says why that is the common fake plan",
       "fake rollback plan" in R.check_backup({})[0][2])
    ok("a named backup that is not there is a blocker",
       titled(R.check_backup({"path": os.path.join(tmp, "nope.sql")}),
              "not there")[0][0] == "BLOCKER")
    tiny = os.path.join(tmp, "tiny.sql")
    io.open(tiny, "w").write("x")
    ok("a suspiciously small backup is major",
       titled(R.check_backup({"path": tiny}), "small")[0][0] == "MAJOR")
    real = os.path.join(tmp, "real.sql")
    io.open(real, "w").write("-" * 5000)
    ok("a real backup with contents named passes",
       not R.check_backup({"path": real, "what_it_contains": "db and files"}))
    ok("a backup directory is measured by what is in it",
       not R.check_backup({"path": tmp, "what_it_contains": "files"}))
    ok("a URL-only backup is flagged as unchecked, not refused",
       sevs(R.check_backup({"url": "https://x.example/b.zip",
                            "what_it_contains": "db"})) == ["MINOR"])

    # ---------------------------------------------------------------- TTL
    ok("no TTL recorded is major", R.check_ttl({})[0][0] == "MAJOR")
    ok("a short TTL is no finding", R.check_ttl({"A x": 300}) == [])
    slow = R.check_ttl({"A x": 300, "NS x": 86400})
    ok("a long TTL is reported with the real revert window",
       slow and slow[0][0] == "MAJOR" and "1440 minutes" in slow[0][1], slow[0][1])
    ok("and it says lowering the TTL late buys nothing",
       "full term" in slow[0][2],
       "resolvers holding the old value keep it")

    # ------------------------------------------------------------- origin
    ok("no old origin recorded is major",
       R.check_origin({})[0][0] == "MAJOR")
    ok("an origin that answers is no finding",
       R.check_origin({"old_origin_url": "http://x"}, fetch=lambda u: 200) == [])
    ok("a redirecting origin is still something to go back to",
       R.check_origin({"old_origin_url": "http://x"}, fetch=lambda u: 301) == [])
    ok("an origin answering 404 is a blocker",
       R.check_origin({"old_origin_url": "http://x"},
                      fetch=lambda u: 404)[0][0] == "BLOCKER")

    def boom(u):
        raise OSError("name or service not known")
    ok("an origin that does not resolve is a blocker",
       R.check_origin({"old_origin_url": "http://x"}, fetch=boom)[0][0]
       == "BLOCKER", "there may be nothing to go back to")

    # ------------------------------------------------------- the whole plan
    complete = json.loads(json.dumps(plan))
    complete["verified_on"] = TODAY.isoformat()
    complete["backup"] = {"path": real, "url": "",
                          "what_it_contains": "database and uploads"}
    complete["old_origin_url"] = "http://203.0.113.10/"
    complete["old_host_paid_until"] = "2027-01-31"
    complete["platform_rollback"] = "Lovable keeps 100 versions; opened and confirmed"
    complete["trigger"] = "any form stops delivering, or mail bounces"
    complete["who"] = "the user, who holds the registrar login"
    complete["ttl_seconds"] = {"A client.example": 300}
    f = R.check(complete, fetch=lambda u: 200, today=TODAY)
    ok("a complete, verified plan has no blockers",
       not [x for x in f if x[0] == "BLOCKER"],
       [x[1] for x in f if x[0] == "BLOCKER"] or "clean")
    ok("and no majors either", not [x for x in f if x[0] == "MAJOR"],
       [x[1] for x in f if x[0] == "MAJOR"] or "clean")
    ok("a gate that can be satisfied is the point", f == [], sevs(f))

    stale = dict(complete)
    stale["verified_on"] = (TODAY - timedelta(days=30)).isoformat()
    ok("a plan verified a month ago is reported as stale",
       titled(R.check(stale, fetch=lambda u: 200, today=TODAY), "days ago")[0][0]
       == "MAJOR")
    fresh = dict(complete)
    fresh["verified_on"] = (TODAY - timedelta(days=3)).isoformat()
    ok("three days old is still current",
       not titled(R.check(fresh, fetch=lambda u: 200, today=TODAY), "days ago"))
    never = dict(complete)
    never["verified_on"] = ""
    ok("never verified is a blocker",
       titled(R.check(never, fetch=lambda u: 200, today=TODAY),
              "never been verified")[0][0] == "BLOCKER")
    junk = dict(complete)
    junk["verified_on"] = "soon"
    ok("a verified_on that is not a date is reported",
       titled(R.check(junk, fetch=lambda u: 200, today=TODAY), "not a date")[0][0]
       == "MAJOR")
    noplat = dict(complete)
    noplat["platform_rollback"] = ""
    ok("no named platform rollback mechanism is major",
       titled(R.check(noplat, fetch=lambda u: 200, today=TODAY),
              "platform rollback")[0][0] == "MAJOR")
    nosite = json.loads(json.dumps(complete))
    nosite["dns_before"]["site"] = {}
    ok("losing the records being changed is a blocker",
       titled(R.check(nosite, fetch=lambda u: 200, today=TODAY),
              "not recorded")[0][0] == "BLOCKER")

    f = R.check(plan, fetch=lambda u: 200, today=TODAY)
    ok("findings come out worst first",
       sevs(f) == sorted(sevs(f), key=lambda s: {"BLOCKER": 0, "MAJOR": 1,
                                                 "MINOR": 2}[s]), sevs(f))

    txt = R.report(complete, [])
    ok("a clean report says it is executable", "Executable as written" in txt)
    ok("the report shows what would be put back",
       "A client.example" in txt and "203.0.113.10" in txt)
    ok("the report carries the TTL lower-bound warning",
       "lower bound" in txt)
    bad = R.report(plan, R.check(plan, fetch=lambda u: 200, today=TODAY))
    ok("a report with blockers says so in as many words",
       "cannot be executed as written" in bad)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
