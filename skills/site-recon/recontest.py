# -*- coding: utf-8 -*-
"""Does recon read a page correctly, and tell a refusal from an absence?

This is the tool the rest of the system is built on - the rollback plan takes
its DNS records from here, the launch gate reads its platform verdict - and it
went without tests while being edited twice in one day. These cover the pure
parsing, the host-platform patterns and the parts of the DNS path that can be
exercised without the network; the live resolvers are stubbed rather than
called, so the suite is deterministic.

    python recontest.py
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import recon  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:120] + "]") if extra else ""))


# ------------------------------------------------------- the host patterns
# Three of these were broken for weeks: a heredoc turned \b into byte 0x08, so
# `\bl5e\.io` and `\bpages\.dev\b` could never match anything at all and the
# platform was silently reported as unknown.
import re  # noqa: E402

HOSTS = [
    ("l5e.io", "Lovable"),
    ("lovable-app-wd-1-4.p.l5e.io", "Lovable"),
    ("thing.pages.dev", "Cloudflare Pages"),
    ("pages.dev", "Cloudflare Pages"),
    ("x.vercel.app", "Vercel"),
    ("vercel", "Vercel"),
    ("site.netlify.app", "Netlify"),
]
for host, want in HOSTS:
    got = [n for n, pat in recon.HOST_PLATFORM if re.search(pat, host, re.I)]
    ok("%s is recognised as %s" % (host, want), want in got,
       ", ".join(got) or "nothing matched")

ok("no host pattern carries a stray control byte",
   not any(chr(8) in pat or chr(12) in pat for _n, pat in recon.HOST_PLATFORM),
   "the bug that made three of them dead")

# ------------------------------------------------------------- page facts

PAGE = """<!doctype html><html lang="en-GB"><head>
<title>  Bright   Dental - Leeds  </title>
<meta name="description" content="A dental practice in Leeds offering implants.">
<meta property="og:image" content="https://bright.test/og.jpg">
<link rel="icon" href="/favicon.ico">
<link rel="apple-touch-icon" href="/apple.png">
</head><body>
<img class="site-logo" src="/img/logo.svg" alt="Bright Dental">
<h1>Dental implants in <span>Leeds</span></h1>
<a href="tel:+44 113 496 0000">Call us</a>
<a href="mailto:hello@bright.test">Email</a>
<p>Or ring 0113 496 0001 during the week.</p>
</body></html>"""

f = recon.page_facts(PAGE, "https://bright.test/")
ok("the title is read and its whitespace collapsed",
   f["title"] == "Bright Dental - Leeds", repr(f["title"]))
ok("the meta description is read",
   f["meta_description"].startswith("A dental practice"), f["meta_description"])
ok("the og:image is read", f["og_image"] == "https://bright.test/og.jpg")
ok("both favicons are collected and kept in order",
   f["favicons"] == ["/favicon.ico", "/apple.png"], f["favicons"])
ok("the logo is found from a class containing 'logo'",
   f["logo_candidates"] == ["/img/logo.svg"], f["logo_candidates"])
ok("the H1 is read with its inner markup stripped",
   f["h1"] == ["Dental implants in Leeds"], f["h1"])
ok("the language is read", f["lang"] == "en-GB", f["lang"])
ok("a tel: link is captured",
   any("113 496 0000" in p for p in f["phones"]), f["phones"])
ok("a phone written in the prose is captured too",
   any("0113 496 0001" in p for p in f["phones"]), f["phones"])
ok("a mailto address is captured",
   "hello@bright.test" in f["emails"], f["emails"])

ok("an empty page returns no facts rather than throwing",
   recon.page_facts("", "https://x.test/") == {})
ok("a page with none of these returns the keys as None",
   recon.page_facts("<html><body>hi</body></html>", "https://x.test/")["title"] is None)

# An image filename ending .png is not an email address, which is what the
# naive pattern collects from `src="logo@2x.png"`.
mail = recon.page_facts(
    '<html><body><img src="brand@2x.png"><a href="mailto:a@b.test">x</a>'
    "</body></html>", "https://x.test/")
ok("an @2x image filename is not reported as an email",
   not any(e.endswith(".png") for e in mail["emails"]), mail["emails"])
ok("and the real address still is", "a@b.test" in mail["emails"], mail["emails"])

dup = recon.page_facts(
    '<html><head><link rel="icon" href="/f.ico"><link rel="shortcut icon" '
    'href="/f.ico"></head><body></body></html>', "https://x.test/")
ok("the same favicon declared twice is listed once",
   dup["favicons"] == ["/f.ico"], dup["favicons"])

# ------------------------------------------------------------------ DNS

calls = {"n": 0}


def fake_get(url, params=None, headers=None, timeout=None):
    """Stand in for the DoH endpoints so the suite never needs the network."""
    calls["n"] += 1
    name = (params or {}).get("name", "")
    rtype = (params or {}).get("type", "")

    class R:
        status_code = 200

        @staticmethod
        def json():
            if name == "split.test":
                # The two resolvers are made to disagree, which is the single
                # most useful signal this tool produces.
                if "google" in url:
                    return {"Answer": [{"data": "192.0.2.10", "TTL": 300}]}
                return {"Answer": [{"data": "198.51.100.10", "TTL": 300}]}
            if name == "ttl.test":
                return {"Answer": [{"data": "ns1.x.test.", "TTL": 86400},
                                   {"data": "ns2.x.test.", "TTL": 3600}]}
            if name == "quoted.test" and rtype == "TXT":
                return {"Answer": [{"data": '"v=spf1 include:x -all"', "TTL": 60}]}
            if name == "empty.test":
                return {}
            if name == "nottl.test":
                return {"Answer": [{"data": "192.0.2.20"}]}
            return {"Answer": [{"data": "192.0.2.1.", "TTL": 120}]}
    return R()


real_get = recon.requests.get
recon.requests.get = fake_get
try:
    vals, note = recon.dns_both("normal.test", "A")
    ok("an answer is returned with its trailing dot stripped",
       vals == ["192.0.2.1"], vals)
    ok("agreeing resolvers produce no note", note is None, note)

    vals, note = recon.dns_both("split.test", "A")
    ok("resolvers that disagree are reported, not silently merged",
       note and "RESOLVERS DISAGREE" in note, note)
    ok("and the note names both answers",
       note and "192.0.2.10" in note and "198.51.100.10" in note, note)

    vals, _n = recon.dns_both("quoted.test", "TXT")
    ok("a TXT record is unquoted", vals == ["v=spf1 include:x -all"], vals)

    vals, _n = recon.dns_both("empty.test", "A")
    ok("a response with no answer section returns nothing", vals == [], vals)

    ok("the shortest TTL is taken, because a revert waits for the longest-lived"
       " cached copy to expire",
       recon.dns_ttl("ttl.test", "NS") == 3600, recon.dns_ttl("ttl.test", "NS"))
    ok("a record with no TTL field returns None rather than zero",
       recon.dns_ttl("nottl.test", "A") is None)
    ok("an empty answer gives no TTL", recon.dns_ttl("empty.test", "A") is None)

    before = calls["n"]
    recon.dns_ttl("ttl.test", "A")
    ok("the TTL lookup asks one resolver, not both",
       calls["n"] - before == 1, calls["n"] - before)


    def boom(*a, **k):
        raise OSError("network is down")

    recon.requests.get = boom
    vals, note = recon.dns_both("x.test", "A")
    ok("a resolver that cannot be reached is reported, not treated as empty",
       vals == [] and note, note)
    ok("a TTL lookup that fails returns None",
       recon.dns_ttl("x.test", "A") is None)
finally:
    recon.requests.get = real_get

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
