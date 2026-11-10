# -*- coding: utf-8 -*-
"""Will the client's mail authenticate, or quietly land in spam?

    python mail.py <domain> [--out <dir>] [--json]

site-recon already records MX, SPF, DMARC and the DKIM selectors. Recording
them is not the same as judging them, and the faults that matter are the ones
that look fine in a DNS panel:

- **Two SPF records.** Not "the second one is ignored" - the result is permerror
  and SPF fails for every message.
- **More than ten DNS-querying terms in SPF.** The same permerror, reached by
  adding one more `include:` for one more sending service. Nothing warns anyone,
  the panel looks tidy, and authentication is simply off. RFC 7208 section 4.6.4
  is explicit: implementations MUST limit those terms to 10 and MUST return
  permerror beyond it. This counts them recursively, which is the only way to
  know.
- **`p=none` in DMARC**, which is monitoring with no enforcement, and is where
  most domains sit for years believing they are protected.

What this cannot tell you: whether a message actually arrived. Authentication
records being coherent is a necessary condition and not a sufficient one -
reputation, content and the receiving server all decide too. The only proof of
delivery is a message in the destination inbox, which is why the skill this
belongs to insists on a real test submission.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# site-recon owns talking to the resolvers, and it asks two of them and reports
# a disagreement. Importing it beats a second, untested copy of that here.
RECON = os.path.join(os.path.dirname(HERE), "site-recon")
sys.path.insert(0, RECON)
try:
    import recon
except Exception:                                    # pragma: no cover
    recon = None

# RFC 7208 4.6.4, read from the RFC: the terms that cause DNS queries are
# include, a, mx, ptr and exists, plus the redirect modifier. MUST be limited
# to 10; beyond that the implementation MUST return permerror. all, ip4, ip6
# and exp do not count.
LOOKUP_TERMS = ("include", "a", "mx", "ptr", "exists", "redirect")
MAX_LOOKUPS = 10
# Same section: void lookups SHOULD be limited to two, with two RECOMMENDED as
# the default. A SHOULD rather than a MUST, so it is reported as very likely to
# fail rather than as certain.
MAX_VOID = 2
SEV_RANK = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2, "NOTE": 3}


def resolver(name, rtype):
    """TXT/MX answers for a name, or [] when nothing is there."""
    if recon is None:
        return []
    vals, _note = recon.dns_both(name, rtype)
    return vals or []


# --------------------------------------------------------------- parsing

def spf_records(txts):
    """Only the records that are actually SPF."""
    return [t for t in (txts or []) if t.strip().lower().startswith("v=spf1")]


def spf_terms(record):
    """(qualifier, term, value) for each term, in order."""
    out = []
    for raw in str(record or "").split()[1:]:
        if not raw:
            continue
        q = "+"
        if raw[0] in "+-~?":
            q, raw = raw[0], raw[1:]
        if "=" in raw and ":" not in raw.split("=")[0]:
            term, _, val = raw.partition("=")
        else:
            term, _, val = raw.partition(":")
        out.append((q, term.lower(), val))
    return out


def all_qualifier(record):
    for q, term, _v in spf_terms(record):
        if term == "all":
            return q
    return None


def count_lookups(domain, resolve=None, _seen=None, _depth=0):
    """Every DNS-querying term in the SPF record, followed through includes.

    Returns {count, void, chain, loop, missing}. The count is what a receiving
    server will count, which is why includes have to be followed: a record with
    three includes can be well over the limit without looking like it.
    """
    resolve = resolve or resolver
    _seen = _seen if _seen is not None else set()
    res = {"count": 0, "void": 0, "chain": [], "loop": False, "missing": []}
    if _depth > 12 or domain.lower() in _seen:
        res["loop"] = True
        return res
    _seen.add(domain.lower())

    recs = spf_records(resolve(domain, "TXT"))
    if not recs:
        res["void"] += 1
        res["missing"].append(domain)
        return res
    for q, term, val in spf_terms(recs[0]):
        if term not in LOOKUP_TERMS:
            continue
        res["count"] += 1
        res["chain"].append(term + (":" + val if val else ""))
        if term in ("include", "redirect") and val:
            sub = count_lookups(val, resolve, _seen, _depth + 1)
            res["count"] += sub["count"]
            res["void"] += sub["void"]
            res["chain"] += ["  " + c for c in sub["chain"]]
            res["missing"] += sub["missing"]
            res["loop"] = res["loop"] or sub["loop"]
    return res


def dmarc_tags(record):
    tags = {}
    for part in str(record or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k:
            tags[k.strip().lower()] = v.strip()
    return tags


# --------------------------------------------------------------- judging

def judge_mx(hosts):
    if not hosts:
        return [{"sev": "BLOCKER", "id": "no-mx",
                 "title": "No MX record: this domain cannot receive mail",
                 "detail": "If the client reads mail at this domain, it is "
                           "broken now. If mail lives elsewhere, that is fine "
                           "and worth recording so nobody 'fixes' it."}]
    return []


def judge_spf(txts, lookups):
    out = []
    recs = spf_records(txts)
    if not recs:
        out.append({"sev": "MAJOR", "id": "no-spf",
                    "title": "No SPF record",
                    "detail": "Nothing states who may send as this domain."})
        return out
    if len(recs) > 1:
        out.append({"sev": "BLOCKER", "id": "spf-multiple",
                    "title": "%d SPF records: SPF fails for every message"
                             % len(recs),
                    "detail": "Two records is a permerror, not 'the first one "
                              "wins'. Merge them into one.",
                    "fix": "One v=spf1 record, with every sender's include in it."})
    rec = recs[0]

    n = lookups.get("count", 0)
    if n > MAX_LOOKUPS:
        out.append({"sev": "BLOCKER", "id": "spf-lookups",
                    "title": "SPF needs %d DNS lookups, over the limit of %d"
                             % (n, MAX_LOOKUPS),
                    "detail": "RFC 7208 requires a receiver to return permerror "
                              "past ten, so SPF is off for every message. "
                              "Nothing in a DNS panel shows this. Chain: "
                              + ", ".join(lookups.get("chain", [])[:12]),
                    "fix": "Flatten or drop an include. Each sending service "
                           "you add costs at least one."})
    elif n >= MAX_LOOKUPS - 2:
        out.append({"sev": "MAJOR", "id": "spf-lookups-near",
                    "title": "SPF uses %d of its %d DNS lookups"
                             % (n, MAX_LOOKUPS),
                    "detail": "The next sending service anyone adds breaks "
                              "authentication for everything."})
    if lookups.get("void", 0) > MAX_VOID:
        out.append({"sev": "MAJOR", "id": "spf-void",
                    "title": "%d SPF lookups resolve to nothing"
                             % lookups["void"],
                    "detail": "Over two void lookups is a permerror in most "
                              "implementations. Missing: "
                              + ", ".join(lookups.get("missing", [])[:5])})
    if lookups.get("loop"):
        out.append({"sev": "MAJOR", "id": "spf-loop",
                    "title": "The SPF include chain loops back on itself"})

    q = all_qualifier(rec)
    if q == "+":
        out.append({"sev": "BLOCKER", "id": "spf-plusall",
                    "title": "SPF ends in +all: anyone may send as this domain",
                    "detail": "This is worse than having no SPF at all, because "
                              "it explicitly authorises every sender on the "
                              "internet.", "fix": "Use -all, or ~all while testing."})
    elif q == "?":
        out.append({"sev": "MAJOR", "id": "spf-neutral",
                    "title": "SPF ends in ?all, which asserts nothing"})
    elif q is None:
        out.append({"sev": "MAJOR", "id": "spf-no-all",
                    "title": "SPF has no all mechanism",
                    "detail": "The default is then neutral, which protects "
                              "nothing. End it explicitly."})
    elif q == "~":
        out.append({"sev": "NOTE", "id": "spf-softfail",
                    "title": "SPF ends in ~all (softfail)",
                    "detail": "Right while a change is bedding in; -all is the "
                              "destination once the sending services are known "
                              "to be complete."})
    if any(t == "ptr" for _q, t, _v in spf_terms(rec)):
        out.append({"sev": "MINOR", "id": "spf-ptr",
                    "title": "SPF uses the ptr mechanism",
                    "detail": "RFC 7208 marks ptr 'do not use'. It is slow and "
                              "some receivers ignore it."})
    return out


def judge_dmarc(record):
    out = []
    if not record:
        return [{"sev": "MAJOR", "id": "no-dmarc",
                 "title": "No DMARC record",
                 "detail": "Nothing tells a receiver what to do when SPF and "
                           "DKIM fail, and nobody receives reports."}]
    t = dmarc_tags(record)
    p = (t.get("p") or "").lower()
    if p == "none":
        out.append({"sev": "MAJOR", "id": "dmarc-none",
                    "title": "DMARC is p=none: monitoring only, no enforcement",
                    "detail": "A failing message is still delivered. This is the "
                              "right first step and the wrong permanent state, "
                              "and it is where most domains sit for years "
                              "believing they are protected.",
                    "fix": "Read the reports, then move to quarantine and on "
                           "to reject."})
    elif p not in ("quarantine", "reject"):
        out.append({"sev": "MAJOR", "id": "dmarc-no-policy",
                    "title": "DMARC has no usable p= policy",
                    "detail": "Found: " + (p or "nothing")})
    if not t.get("rua"):
        out.append({"sev": "MINOR", "id": "dmarc-no-rua",
                    "title": "DMARC has no rua address, so no reports arrive",
                    "detail": "Without reports there is no way to know which "
                              "senders are failing before enforcing."})
    pct = t.get("pct")
    if pct and pct.strip() not in ("100", ""):
        out.append({"sev": "MINOR", "id": "dmarc-pct",
                    "title": "DMARC applies to only %s%% of mail" % pct,
                    "detail": "The rest is treated as p=none."})
    return out


def judge_dkim(selectors):
    out = []
    if not selectors:
        return [{"sev": "MAJOR", "id": "no-dkim",
                 "title": "No DKIM selector found",
                 "detail": "Only the common selector names were tried, so a "
                           "custom one would be missed - confirm with the "
                           "sending service rather than concluding there is "
                           "none."}]
    for sel, val in sorted(selectors.items()):
        v = str(val or "")
        m = re.search(r"\bp=([^;\s]*)", v)
        if m is not None and not m.group(1):
            out.append({"sev": "MAJOR", "id": "dkim-revoked",
                        "title": "DKIM selector '%s' has an empty public key"
                                 % sel,
                        "detail": "An empty p= means the key is revoked. Mail "
                                  "signed with it fails."})
    return out


def sort_findings(items):
    return sorted(items, key=lambda f: (SEV_RANK.get(f["sev"], 9), f["title"]))


def report(data):
    f = data["findings"]
    n = lambda s: sum(1 for x in f if x["sev"] == s)
    L = ["# Mail authentication - " + data["domain"], ""]
    L.append("%d finding(s): %d blocker, %d major, %d minor, %d note."
             % (len(f), n("BLOCKER"), n("MAJOR"), n("MINOR"), n("NOTE")))
    L.append("")
    if not f:
        L.append("The authentication records are coherent.")
        L.append("")
    for x in f:
        L.append("## %s - %s" % (x["sev"], x["title"]))
        if x.get("detail"):
            L.append(x["detail"])
        if x.get("fix"):
            L.append("Fix: " + x["fix"])
        L.append("")
    L.append("## What was read")
    L.append("  MX: %s" % (", ".join(data["mx"]) or "Missing"))
    L.append("  SPF: %s" % (data["spf"] or "Missing"))
    L.append("  SPF DNS lookups: %d of %d%s"
             % (data["lookups"]["count"], MAX_LOOKUPS,
                ("  [" + ", ".join(data["lookups"]["chain"][:10]) + "]")
                if data["lookups"]["chain"] else ""))
    L.append("  DMARC: %s" % (data["dmarc"] or "Missing"))
    L.append("  DKIM selectors: %s"
             % (", ".join(sorted(data["dkim"])) or "Missing"))
    L.append("")
    L.append("## The limit of this check")
    L.append("Coherent authentication records are necessary and not sufficient. "
             "They do not prove a message arrived: reputation, content and the "
             "receiving server decide that too. **Send a real test and confirm "
             "it in the destination inbox** - the inbox, not the send log, and "
             "check the spam folder before calling it delivered.")
    return "\n".join(L)


def run(domain, resolve=None):
    resolve = resolve or resolver
    txts = resolve(domain, "TXT")
    mx = resolve(domain, "MX")
    dmarc_txt = [t for t in resolve("_dmarc." + domain, "TXT")
                 if t.strip().lower().startswith("v=dmarc1")]
    dkim = {}
    sels = (recon.DKIM_SELECTORS if recon else
            ["google", "default", "selector1", "selector2", "k1"])
    for sel in sels:
        v = resolve("%s._domainkey.%s" % (sel, domain), "TXT")
        if v:
            dkim[sel] = v[0]

    lookups = count_lookups(domain, resolve)
    findings = []
    findings += judge_mx(mx)
    findings += judge_spf(txts, lookups)
    findings += judge_dmarc(dmarc_txt[0] if dmarc_txt else None)
    findings += judge_dkim(dkim)
    recs = spf_records(txts)
    return {"domain": domain, "mx": mx, "spf": recs[0] if recs else None,
            "spf_count": len(recs), "dmarc": dmarc_txt[0] if dmarc_txt else None,
            "dkim": dkim, "lookups": lookups,
            "findings": sort_findings(findings)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    if recon is None:
        print("site-recon's resolver could not be imported from %s" % RECON)
        return 2
    domain = args[0].replace("https://", "").replace("http://", "").strip("/")
    data = run(domain)
    text = report(data)
    out = ""
    if "--out" in sys.argv:
        i = sys.argv.index("--out")
        out = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    if out:
        os.makedirs(out, exist_ok=True)
        io.open(os.path.join(out, "mail.md"), "w", encoding="utf-8",
                newline="\n").write(text + "\n")
        io.open(os.path.join(out, "mail.json"), "w", encoding="utf-8",
                newline="\n").write(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2) if "--json" in sys.argv else text)
    return 1 if any(f["sev"] == "BLOCKER" for f in data["findings"]) else 0


if __name__ == "__main__":
    sys.exit(main())
