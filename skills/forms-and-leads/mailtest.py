# -*- coding: utf-8 -*-
"""Does the mail check count SPF lookups the way a receiver will?

The lookup count is the reason this exists. A record with three includes looks
tidy and can be well over the limit, at which point SPF is off for every
message and nothing anywhere says so. Counting it wrong in the low direction
would be worse than not counting it, so the recursion is tested against a fake
DNS with a known answer.

    python mailtest.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mail as M  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:120] + "]") if extra else ""))


ids = lambda l: [f["id"] for f in l]
has = lambda l, i: i in ids(l)
sev = lambda l, i: next((f["sev"] for f in l if f["id"] == i), None)

# A fake zone, so the recursion has a known answer.
ZONE = {
    # 5 visible terms, 14 real lookups once the includes are followed.
    "deep.test": {"TXT": ["v=spf1 include:a.test include:b.test include:c.test mx a -all"]},
    "a.test": {"TXT": ["v=spf1 include:a1.test include:a2.test ip4:192.0.2.1 ~all"]},
    "a1.test": {"TXT": ["v=spf1 a mx ~all"]},
    "a2.test": {"TXT": ["v=spf1 a ~all"]},
    "b.test": {"TXT": ["v=spf1 include:b1.test a ~all"]},
    "b1.test": {"TXT": ["v=spf1 mx ~all"]},
    "c.test": {"TXT": ["v=spf1 a ~all"]},
    # Flattened the way a large sender does it: one include, and everything
    # inside it is ip4/ip6, which the RFC excludes from the count.
    "flat.test": {"TXT": ["v=spf1 include:net.test -all"]},
    "net.test": {"TXT": ["v=spf1 ip4:192.0.2.0/24 ip6:2001:db8::/32 ~all"]},
    # A loop.
    "loop.test": {"TXT": ["v=spf1 include:loop2.test -all"]},
    "loop2.test": {"TXT": ["v=spf1 include:loop.test -all"]},
    # Includes that resolve to nothing.
    "void.test": {"TXT": ["v=spf1 include:gone1.test include:gone2.test "
                          "include:gone3.test -all"]},
    "clean.test": {
        "TXT": ["v=spf1 include:net.test -all", "MS=verification"],
        "MX": ["10 mail.clean.test"],
    },
    "_dmarc.clean.test": {"TXT": ["v=DMARC1; p=reject; rua=mailto:r@clean.test"]},
}


def fake(name, rtype):
    return ZONE.get(name, {}).get(rtype, [])


# --------------------------------------------------------------- parsing

ok("an SPF record is picked out of a pile of TXT records",
   M.spf_records(["MS=abc", "v=spf1 -all", "google-site-verification=x"])
   == ["v=spf1 -all"])
ok("a domain with no SPF among its TXT records returns none",
   M.spf_records(["MS=abc", "Z29vZ2xl"]) == [])

terms = M.spf_terms("v=spf1 +a -mx ~include:x.test ?ip4:192.0.2.1 redirect=y.test -all")
ok("each term keeps its qualifier",
   [t[0] for t in terms] == ["+", "-", "~", "?", "+", "-"], [t[0] for t in terms])
ok("the mechanism name is lowercased and split from its value",
   ("~", "include", "x.test") in terms, terms)
ok("a modifier written with = is parsed",
   ("+", "redirect", "y.test") in terms, terms)
ok("the all qualifier is read", M.all_qualifier("v=spf1 a ~all") == "~")
ok("a record with no all mechanism reports none",
   M.all_qualifier("v=spf1 a mx") is None)

# ------------------------------------------------------- counting lookups

deep = M.count_lookups("deep.test", fake)
ok("includes are followed and the real count found",
   deep["count"] == 14, deep["count"])
ok("the chain is recorded so the cost can be traced",
   "include:a.test" in deep["chain"] and any("a1" in c for c in deep["chain"]),
   deep["chain"][:4])
ok("the chain indents what each include pulled in",
   any(c.startswith("  ") for c in deep["chain"]))

flat = M.count_lookups("flat.test", fake)
ok("ip4 and ip6 inside an include cost nothing",
   flat["count"] == 1, flat["count"])
ok("which is how a large sender stays under the limit",
   flat["count"] < M.MAX_LOOKUPS)

ok("all, ip4 and ip6 are not counted at this level",
   M.count_lookups("net.test", fake)["count"] == 0)

loop = M.count_lookups("loop.test", fake)
ok("an include loop is detected rather than recursed forever",
   loop["loop"] is True)

void = M.count_lookups("void.test", fake)
ok("includes that resolve to nothing are counted as void lookups",
   void["void"] == 3, void["void"])
ok("and the missing names are recorded",
   sorted(void["missing"]) == ["gone1.test", "gone2.test", "gone3.test"],
   void["missing"])

ok("a domain with no SPF at all is one void lookup",
   M.count_lookups("nothing.test", fake)["void"] == 1)

# ---------------------------------------------------------- judging SPF

ok("no SPF record is a major finding",
   sev(M.judge_spf([], {"count": 0}), "no-spf") == "MAJOR")
two = M.judge_spf(["v=spf1 a -all", "v=spf1 mx -all"], {"count": 2})
ok("two SPF records is a blocker, not 'the first one wins'",
   sev(two, "spf-multiple") == "BLOCKER")
ok("and it says SPF fails for every message",
   "fails for every message" in
   next(f for f in two if f["id"] == "spf-multiple")["title"])

over = M.judge_spf(["v=spf1 include:a -all"], {"count": 14, "chain": ["include:a"]})
ok("over ten lookups is a blocker",
   sev(over, "spf-lookups") == "BLOCKER")
ok("and the finding states the permerror consequence",
   "permerror" in next(f for f in over if f["id"] == "spf-lookups")["detail"])
ok("and it says nothing in a DNS panel shows it",
   "DNS panel" in next(f for f in over if f["id"] == "spf-lookups")["detail"],
   "which is why it goes unnoticed")
ok("exactly ten is not over the limit",
   not has(M.judge_spf(["v=spf1 a -all"], {"count": 10}), "spf-lookups"))
ok("eight of ten is a major warning that the next one breaks it",
   sev(M.judge_spf(["v=spf1 a -all"], {"count": 8}), "spf-lookups-near") == "MAJOR")
ok("a comfortable count raises nothing",
   not has(M.judge_spf(["v=spf1 a -all"], {"count": 3}), "spf-lookups-near"))

ok("+all is a blocker and is called worse than no SPF",
   sev(M.judge_spf(["v=spf1 a +all"], {"count": 1}), "spf-plusall") == "BLOCKER")
ok("?all asserts nothing and is major",
   sev(M.judge_spf(["v=spf1 a ?all"], {"count": 1}), "spf-neutral") == "MAJOR")
ok("a record with no all mechanism is major",
   sev(M.judge_spf(["v=spf1 a mx"], {"count": 2}), "spf-no-all") == "MAJOR")
ok("~all is a note, right while a change beds in",
   sev(M.judge_spf(["v=spf1 a ~all"], {"count": 1}), "spf-softfail") == "NOTE")
ok("-all raises no qualifier finding",
   not any(i.startswith("spf-") and i not in ("spf-lookups-near",)
           for i in ids(M.judge_spf(["v=spf1 a -all"], {"count": 1}))),
   ids(M.judge_spf(["v=spf1 a -all"], {"count": 1})))
ok("the ptr mechanism is reported as do-not-use",
   sev(M.judge_spf(["v=spf1 ptr -all"], {"count": 1}), "spf-ptr") == "MINOR")
ok("too many void lookups is reported",
   sev(M.judge_spf(["v=spf1 a -all"], {"count": 3, "void": 3, "missing": ["x"]}),
       "spf-void") == "MAJOR")
ok("a loop is reported",
   has(M.judge_spf(["v=spf1 a -all"], {"count": 3, "loop": True}), "spf-loop"))

# --------------------------------------------------------- judging DMARC

ok("no DMARC is major", sev(M.judge_dmarc(None), "no-dmarc") == "MAJOR")
none = M.judge_dmarc("v=DMARC1; p=none; rua=mailto:r@x.test")
ok("p=none is reported as monitoring without enforcement",
   sev(none, "dmarc-none") == "MAJOR")
ok("and it says this is where most domains sit for years",
   "believing they are protected" in
   next(f for f in none if f["id"] == "dmarc-none")["detail"])
ok("p=reject with a report address is clean",
   M.judge_dmarc("v=DMARC1; p=reject; rua=mailto:r@x.test") == [])
ok("p=quarantine is accepted as enforcement",
   not has(M.judge_dmarc("v=DMARC1; p=quarantine; rua=mailto:r@x.test"),
           "dmarc-none"))
ok("a missing rua is reported, because nobody sees the reports",
   sev(M.judge_dmarc("v=DMARC1; p=reject"), "dmarc-no-rua") == "MINOR")
ok("partial enforcement is reported with its percentage",
   "20%" in next(f for f in M.judge_dmarc("v=DMARC1; p=reject; pct=20; rua=mailto:r@x")
                 if f["id"] == "dmarc-pct")["title"])
ok("pct=100 is not reported",
   not has(M.judge_dmarc("v=DMARC1; p=reject; pct=100; rua=mailto:r@x"), "dmarc-pct"))
ok("a DMARC record with no policy at all is reported",
   has(M.judge_dmarc("v=DMARC1; rua=mailto:r@x"), "dmarc-no-policy"))

# ---------------------------------------------------------- judging DKIM

ok("no selector found says the list of names tried was not exhaustive",
   "custom one would be missed" in M.judge_dkim({})[0]["detail"],
   "absence of a common selector is not absence of DKIM")
ok("a revoked key with an empty p= is reported",
   sev(M.judge_dkim({"s1": "v=DKIM1; k=rsa; p="}), "dkim-revoked") == "MAJOR")
ok("a real key is not reported",
   M.judge_dkim({"s1": "v=DKIM1; k=rsa; p=MIGfMA0GCSqGSIb3"}) == [])

# ------------------------------------------------------------ judging MX

ok("no MX at all is a blocker", sev(M.judge_mx([]), "no-mx") == "BLOCKER")
ok("and it allows for mail living elsewhere on purpose",
   "worth recording so nobody 'fixes' it" in M.judge_mx([])[0]["detail"])
ok("an MX record raises nothing", M.judge_mx(["10 mail.x.test"]) == [])

# ---------------------------------------------------------- the whole run

d = M.run("clean.test", fake)
ok("a well configured domain comes back with no blockers",
   not [f for f in d["findings"] if f["sev"] == "BLOCKER"],
   ids(d["findings"]))
ok("the SPF record is reported back", d["spf"].startswith("v=spf1"))
ok("the DMARC record is reported back", "p=reject" in (d["dmarc"] or ""))
ok("the lookup count is included", d["lookups"]["count"] == 1, d["lookups"])

text = M.report(d)
ok("the report states that records being right does not prove delivery",
   "necessary and not sufficient" in text)
ok("and it says to check the inbox rather than the send log",
   "not the send log" in text and "spam folder" in text)
ok("the report shows the lookup count against the limit",
   "SPF DNS lookups: 1 of 10" in text, [l for l in text.splitlines() if "lookups" in l])
ok("an absent value is written as Missing, never Not Found",
   "Not Found" not in text and "N/A" not in text)

bad = M.run("deep.test", fake)
ok("a domain over the lookup limit reports a blocker",
   any(f["sev"] == "BLOCKER" for f in bad["findings"]), ids(bad["findings"]))
ok("findings come out worst first",
   [f["sev"] for f in bad["findings"]]
   == sorted([f["sev"] for f in bad["findings"]], key=lambda s: M.SEV_RANK[s]))

ok("the RFC limits are the ones the RFC states",
   M.MAX_LOOKUPS == 10 and M.MAX_VOID == 2)
ok("only the terms the RFC names as DNS-querying are counted",
   sorted(M.LOOKUP_TERMS) == sorted(["include", "a", "mx", "ptr", "exists",
                                     "redirect"]),
   "all, ip4, ip6 and exp are excluded by the RFC")

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
