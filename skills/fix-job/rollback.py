# -*- coding: utf-8 -*-
"""Is there a way back from this launch, and has anyone checked?

    python rollback.py <project> --build --domain example.com [--recon <dir>]
    python rollback.py <project>                     check the plan is real
    python rollback.py <project> --json

`--build` writes `<project>/.claude-context/rollback.json`, filling in whatever
the recon output already knows - the records that are about to change, the mail
records that must survive, the host, the TTL - and leaving the fields only a
human can answer empty and named.

Without `--build` it checks the plan, and the checking is the point. Every
launch has a rollback plan in the sense that somebody will say "we can just
point it back". That sentence is not a plan:

- "Restore from backup" with no backup path is the commonest fake plan there
  is, and it is only discovered at the worst possible moment.
- Pointing the site records back does not bring mail back if the mail records
  were replaced too. site-recon's own note on this is blunt: that is the one
  that loses a client.
- The old host gets cancelled on launch day, by someone being tidy, and then
  there is nothing to go back to.
- A plan verified three weeks ago describes a site that has since changed.

So this reports a plan that cannot be executed as a BLOCKER, and `fix-job`
refuses to close a golive while one is standing.
"""
import io
import json
import os
import re
import sys
from datetime import date, datetime

STALE_DAYS = 14
# Above this a revert is not a quick fix and the plan has to say so out loud.
FAST_TTL = 3600
MIN_BACKUP_BYTES = 1024

HUMAN_FIELDS = ("backup", "old_origin_url", "old_host_paid_until",
                "platform_rollback", "trigger", "who")


def plan_path(project):
    return os.path.join(project, ".claude-context", "rollback.json")


def load_recon(project, explicit=None):
    """The most recent recon.json under the project, if there is one."""
    if explicit:
        p = explicit if explicit.endswith(".json") \
            else os.path.join(explicit, "recon.json")
        if os.path.isfile(p):
            return json.loads(io.open(p, encoding="utf-8").read()), p
        return None, None
    best, when = None, None
    for dp, dn, fn in os.walk(os.path.join(project, ".claude-context")):
        for f in fn:
            if f != "recon.json":
                continue
            p = os.path.join(dp, f)
            m = os.path.getmtime(p)
            if when is None or m > when:
                best, when = p, m
    if not best:
        return None, None
    try:
        return json.loads(io.open(best, encoding="utf-8").read()), best
    except Exception:
        return None, None


def build(project, domain, recon_dir=None):
    """A plan pre-filled with what is already known, and honest about the rest."""
    R, src = load_recon(project, recon_dir)
    dns = (R or {}).get("dns") or {}
    domain = domain or (R or {}).get("domain") or ""

    # What a launch repoints, and what must survive it, kept apart on purpose.
    site_keys = [k for k in dns if re.match(r"^(A|AAAA|CNAME) ", k)]
    mail_keys = [k for k in dns if k.startswith("MX ")]
    ns_keys = [k for k in dns if k.startswith("NS ")]

    spf = ((R or {}).get("spf") or {}).get("records") or []
    dmarc = ((R or {}).get("dmarc") or {}).get("record")
    dkim = (R or {}).get("dkim_selectors_found") or {}
    ttl = (R or {}).get("ttl") or {}
    host = (R or {}).get("hosting") or {}
    apex = ((R or {}).get("http") or {}).get("apex") or {}

    plan = {
        "domain": domain,
        "built": date.today().isoformat(),
        "verified_on": "",
        "from_recon": src or "",
        "dns_before": {
            "site": {k: dns[k] for k in sorted(site_keys)},
            "nameservers": {k: dns[k] for k in sorted(ns_keys)},
            "mail": {
                "mx": {k: dns[k] for k in sorted(mail_keys)},
                "spf": spf,
                "dmarc": dmarc,
                "dkim_selectors": sorted(dkim),
                # Whether the recon pass saw any mail at all, so a domain that
                # has none is not blocked for failing to record what does not
                # exist. Only set when a recon was actually read: absent means
                # unknown, which stays a blocker.
                "found_by_recon": (bool(mail_keys or spf) if R else None),
            },
        },
        "ttl_seconds": ttl,
        "ttl_note": ("A public resolver reports the time left on its cached "
                     "copy, so these are lower bounds. Read the zone's own TTL "
                     "in the DNS panel before promising a revert window."),
        "old_host": {
            "server": apex.get("server"),
            "ips": host.get("ips") or [],
            "reverse_dns": host.get("reverse_dns") or {},
            "behind_cloudflare": host.get("behind_cloudflare"),
        },
        # Nothing here can be discovered. Left empty and named, because an
        # empty field is a question and a guessed one is a false answer.
        "backup": {"path": "", "url": "", "what_it_contains": ""},
        "old_origin_url": "",
        "old_host_paid_until": "",
        "platform_rollback": "",
        "trigger": "",
        "who": "",
    }
    p = plan_path(project)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return plan, p


# ----------------------------------------------------------------- checking

def check_backup(b):
    """A named backup that is actually there, with something in it."""
    out = []
    path, url = (b or {}).get("path") or "", (b or {}).get("url") or ""
    if not path and not url:
        out.append(("BLOCKER", "No backup is named",
                    "'restore from backup' with no path or URL is the most "
                    "common fake rollback plan, and it fails at the worst "
                    "moment. Name the file."))
        return out
    if path:
        if not os.path.exists(path):
            out.append(("BLOCKER", "The named backup is not there",
                        "%s does not exist. A plan pointing at a missing file "
                        "is worse than no plan, because it is believed." % path))
        else:
            size = (os.path.getsize(path) if os.path.isfile(path)
                    else sum(os.path.getsize(os.path.join(dp, f))
                             for dp, _dn, fn in os.walk(path) for f in fn))
            if size < MIN_BACKUP_BYTES:
                out.append(("MAJOR", "The backup is suspiciously small",
                            "%s is %d bytes. Open it before trusting it."
                            % (path, size)))
    if url and not path:
        out.append(("MINOR", "The backup is a URL, so its contents are not "
                    "checked here", "Download it once and confirm it opens."))
    if not (b or {}).get("what_it_contains"):
        out.append(("MINOR", "The backup does not say what it contains",
                    "Database only, files only, or both - it decides what a "
                    "restore actually gets back."))
    return out


def check_mail(mail):
    """The records that must survive a repoint, judged on their own.

    Nothing recorded means one of two very different things, and treating them
    alike makes the check useless. A domain that carries the client's mail and
    has no MX written down is a blocker. A preview host or a domain that has
    never had mail is not - and demanding MX records of it would block every
    such launch forever, which is how a gate gets forced open by habit. The
    recon pass already knows which case it is, so `build` records that and
    this reads it rather than guessing.
    """
    out = []
    mail = mail or {}
    found = mail.get("found_by_recon")
    if not mail.get("mx"):
        if found is False:
            out.append(("MINOR", "No mail records exist on this domain",
                        "The recon pass found no MX and no SPF, so there is no "
                        "mail to lose. Confirm that is right for this client "
                        "before the launch - a domain whose mail is hosted "
                        "elsewhere looks identical from here."))
            return out
        out.append(("BLOCKER", "The mail records are not recorded",
                    "Putting the site records back does not bring mail back if "
                    "the MX records were replaced too. This is the one that "
                    "loses a client."))
    if not mail.get("spf"):
        out.append(("MAJOR", "No SPF record is recorded",
                    "Restored mail that fails SPF is mail that silently goes "
                    "to spam, which looks like working mail from the inside."))
    if not mail.get("dmarc"):
        out.append(("MINOR", "No DMARC record is recorded", ""))
    return out


def check_ttl(ttl):
    out = []
    if not ttl:
        out.append(("MAJOR", "No TTL is recorded",
                    "Without it nobody knows whether a revert takes five "
                    "minutes or a day, which is the first thing asked when a "
                    "launch goes wrong."))
        return out
    worst = max(ttl.values())
    if worst > FAST_TTL:
        mins = worst // 60
        out.append(("MAJOR", "A revert would take at least %d minutes" % mins,
                    "The slowest recorded TTL is %ds (%s). Lower the TTL "
                    "**before** the launch, and do it at least one old-TTL "
                    "period in advance - resolvers already holding the old "
                    "value keep it for its full term, so lowering it an hour "
                    "before a change buys nothing."
                    % (worst, max(ttl, key=ttl.get))))
    return out


def check_origin(plan, fetch=None):
    """Is there anything still serving at the old origin?"""
    url = plan.get("old_origin_url") or ""
    if not url:
        return [("MAJOR", "No old origin is recorded",
                 "Once DNS moves, the old site cannot be reached by its "
                 "hostname, so without the origin's own address there is no "
                 "way to check there is still something to go back to.")]
    if fetch is None:
        try:
            import requests

            def fetch(u):
                r = requests.get(u, timeout=15,
                                 headers={"User-Agent": "rollback-check"})
                return r.status_code
        except Exception:
            return [("MINOR", "The old origin was not checked",
                     "requests is not available here.")]
    try:
        code = fetch(url)
    except Exception as e:
        return [("BLOCKER", "The old origin did not answer",
                 "%s - %s. There may be nothing to go back to."
                 % (url, str(e)[:80]))]
    if code is None or code >= 400:
        return [("BLOCKER", "The old origin answers %s" % code,
                 "%s is not serving the old site any more." % url)]
    return []


def check(plan, fetch=None, today=None):
    """Everything wrong with the plan, worst first."""
    out = []
    if not plan:
        return [("BLOCKER", "There is no rollback plan",
                 "Build one with --build before the launch, not after it.")]

    today = today or date.today()
    v = plan.get("verified_on") or ""
    if not v:
        out.append(("BLOCKER", "The plan has never been verified",
                    "Fill in verified_on once you have actually confirmed the "
                    "backup opens and the old host still answers. A plan "
                    "nobody has tested is a sentence, not a plan."))
    else:
        try:
            age = (today - datetime.strptime(v[:10], "%Y-%m-%d").date()).days
            if age > STALE_DAYS:
                out.append(("MAJOR", "The plan was last verified %d days ago"
                            % age, "The site has changed since. Check it again."))
        except Exception:
            out.append(("MAJOR", "verified_on is not a date", repr(v)[:40]))

    before = plan.get("dns_before") or {}
    if not before.get("site"):
        out.append(("BLOCKER", "The records being changed are not recorded",
                    "There is nothing to put back."))
    out += check_mail(before.get("mail"))
    out += check_ttl(plan.get("ttl_seconds"))
    out += check_backup(plan.get("backup"))
    out += check_origin(plan, fetch)

    if not plan.get("platform_rollback"):
        out.append(("MAJOR", "No platform rollback mechanism is named",
                    "Lovable keeps versions, Vercel and Netlify keep "
                    "deployments, WordPress needs a plugin or a file restore, "
                    "and git needs a revert. Which one, and has anyone opened "
                    "it?"))
    if not plan.get("old_host_paid_until"):
        out.append(("MINOR", "No date for how long the old host stays up",
                    "Old hosting gets cancelled on launch day by someone being "
                    "tidy."))
    if not plan.get("trigger"):
        out.append(("MINOR", "No trigger is written down",
                    "A plan with no 'we revert if...' never gets used; someone "
                    "keeps trying one more fix instead."))
    if not plan.get("who"):
        out.append(("MINOR", "Nobody is named as able to execute it",
                    "A plan that needs an access nobody present has is not "
                    "available on the day."))

    rank = {"BLOCKER": 0, "MAJOR": 1, "MINOR": 2}
    return sorted(out, key=lambda f: (rank.get(f[0], 9), f[1]))


def report(plan, findings):
    L = []
    dom = (plan or {}).get("domain") or "?"
    L.append("# Rollback plan - %s" % dom)
    L.append("")
    counts = {s: sum(1 for f in findings if f[0] == s)
              for s in ("BLOCKER", "MAJOR", "MINOR")}
    if not findings:
        L.append("Executable as written. Verified %s."
                 % (plan.get("verified_on") or "?"))
    else:
        L.append("%d blocker, %d major, %d minor."
                 % (counts["BLOCKER"], counts["MAJOR"], counts["MINOR"]))
        if counts["BLOCKER"]:
            L.append("")
            L.append("**This plan cannot be executed as written.**")
    L.append("")
    for sev, title, detail in findings:
        L.append("## %s - %s" % (sev, title))
        if detail:
            L.append(detail)
        L.append("")
    if plan:
        before = plan.get("dns_before") or {}
        L.append("## What would be put back")
        for k, v in sorted((before.get("site") or {}).items()):
            L.append("  %-40s %s" % (k, ", ".join(v)))
        for k, v in sorted((before.get("nameservers") or {}).items()):
            L.append("  %-40s %s" % (k, ", ".join(v)))
        mail = before.get("mail") or {}
        for k, v in sorted((mail.get("mx") or {}).items()):
            L.append("  %-40s %s" % (k, ", ".join(v)))
        if mail.get("spf"):
            L.append("  %-40s %s" % ("SPF", "; ".join(mail["spf"])[:100]))
        L.append("")
        if plan.get("ttl_seconds"):
            L.append("## How long a revert takes")
            for k, v in sorted(plan["ttl_seconds"].items()):
                L.append("  %-40s %ss" % (k, v))
            L.append(plan.get("ttl_note") or "")
    return "\n".join(L)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {}
    rest = sys.argv[1:]
    for i, a in enumerate(rest):
        if a.startswith("--"):
            nxt = rest[i + 1] if i + 1 < len(rest) else None
            flags[a[2:]] = nxt if nxt and not nxt.startswith("--") else True
    project = os.path.abspath(args[0] if args else os.getcwd())
    if not os.path.isdir(project):
        print("no such project folder: %s" % project)
        return 2

    if flags.get("build"):
        dom = flags.get("domain")
        plan, p = build(project, dom if isinstance(dom, str) else "",
                        flags.get("recon") if isinstance(flags.get("recon"), str)
                        else None)
        print("wrote %s" % p)
        print("Filled in from %s" % (plan["from_recon"] or "nothing - no recon "
                                     "output found, so the records are empty"))
        print("\nThese cannot be discovered and are empty on purpose:")
        for f in HUMAN_FIELDS:
            print("  %s" % f)
        print("\nFill them in, confirm the backup opens and the old host still")
        print("answers, then set verified_on. Until then this is a blocker.")
        return 0

    p = plan_path(project)
    plan = (json.loads(io.open(p, encoding="utf-8").read())
            if os.path.isfile(p) else None)
    findings = check(plan)
    if flags.get("json"):
        print(json.dumps({"findings": [{"sev": s, "title": t, "detail": d}
                                       for s, t, d in findings],
                          "plan": plan}, indent=2, ensure_ascii=False))
    else:
        print(report(plan, findings))
    return 1 if any(f[0] == "BLOCKER" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
