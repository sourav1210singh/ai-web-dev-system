# -*- coding: utf-8 -*-
"""Site recon - everything about a client's existing site that a machine can find.

    python recon.py <domain-or-url> [--out <dir>] [--json]

Writes <out>/recon.md and <out>/recon.json.

Deliberately asks TWO independent resolvers for every DNS answer and flags any
disagreement, because a hosting control panel can show a zone that is not the
one being served. Nothing here needs a login; what needs a login is listed at
the end as questions for the client.
"""
import json, os, re, socket, ssl, sys, datetime

try:
    import requests
except ImportError:
    print("needs requests:  pip install requests")
    sys.exit(2)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 20

RESOLVERS = [
    ("Google", "https://dns.google/resolve", {}),
    ("Cloudflare", "https://cloudflare-dns.com/dns-query",
     {"Accept": "application/dns-json"}),
]

DKIM_SELECTORS = ["google", "default", "selector1", "selector2", "k1", "k2",
                  "mail", "dkim", "s1", "s2", "zoho", "resend", "sendgrid",
                  "mandrill", "pm", "postmark"]

PLATFORM = [
    ("WordPress", r"wp-content|wp-includes|wp-json|/wp-admin"),
    ("Elementor", r"elementor"),
    ("Kadence", r"kadence"),
    # a bare "divi" matches Tailwind's divide-y and divide-x utilities, and
    # reported a React site as Divi. A wrong platform sends the whole job
    # down the wrong route, so this needs a real Divi marker.
    ("Divi", r"et_pb_|/themes/[Dd]ivi|divi-builder|divi\.css"),
    ("WooCommerce", r"woocommerce"),
    ("Webflow", r"webflow\.(io|com)|data-wf-page"),
    ("Lovable", r"lovable\.(app|dev)|gpteng|lovable_verify"),
    ("Next.js", r"/_next/|__NEXT_DATA__"),
    ("TanStack Start", r"tanstack"),
    ("Astro", r"astro-island|data-astro"),
    ("React", r"react(-dom)?[@.\-]|__REACT"),
    ("Vue", r"__NUXT__|vue\.runtime"),
    ("Shopify", r"cdn\.shopify|shopify\.com"),
    ("Squarespace", r"squarespace"),
    ("Wix", r"wix\.com|wixstatic"),
    ("GoHighLevel", r"gohighlevel|msgsndr"),
    ("Tailwind", r"tailwind|tw-"),
]

# Read from the hostname and the reverse DNS of the serving IPs, not from
# the markup. This is how a site with no give-away in its HTML still gets
# identified.
HOST_PLATFORM = [
    ("Lovable", r"lovable\.app|lovable-app|l5e\.io"),
    ("Vercel", r"vercel\.app|vercel-dns|vercel"),
    ("Netlify", r"netlify\.app|netlify\.com"),
    ("WP Engine", r"wpengine|wpenginepowered"),
    ("Shopify", r"shopify|myshopify"),
    ("Webflow", r"webflow"),
    ("GitHub Pages", r"github\.io|githubusercontent"),
    ("Cloudflare Pages", r"pages\.dev"),
    ("Supabase", r"supabase\.co"),
]

ANALYTICS = [
    ("GA4", r"G-[A-Z0-9]{8,12}"),
    ("Universal Analytics", r"UA-\d{4,10}-\d{1,4}"),
    ("Google Tag Manager", r"GTM-[A-Z0-9]{5,9}"),
    ("Google Ads", r"AW-\d{9,12}"),
    ("Meta Pixel", r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,20})"),
    ("Hotjar", r"hjid\s*[:=]\s*(\d{6,9})"),
    ("Clarity", r"clarity\.ms/tag/([a-z0-9]{8,12})"),
    ("HubSpot", r"js\.hs-scripts\.com/(\d{6,10})"),
]

VERIFY_TXT = {
    "_lovable": "Lovable domain verification",
    "_lovable-email": "Lovable email verification",
    "_dmarc": "DMARC policy",
    "_domainkey": "DKIM parent",
}


def out(d, k, v):
    d[k] = v
    return v


# ------------------------------------------------------------------ DNS
def dns_query(name, rtype, resolver):
    label, url, headers = resolver
    try:
        r = requests.get(url, params={"name": name, "type": rtype},
                         headers=dict(headers, **{"User-Agent": UA}),
                         timeout=TIMEOUT)
        j = r.json()
    except Exception as e:
        return None, str(e)[:90]
    ans = []
    for a in (j.get("Answer") or []):
        data = a.get("data", "")
        ans.append(data.strip('"') if rtype == "TXT" else data.rstrip("."))
    return sorted(set(ans)), None


def dns_both(name, rtype):
    """Ask both resolvers. Returns (answers, note)."""
    res, errs = {}, []
    for rv in RESOLVERS:
        a, err = dns_query(name, rtype, rv)
        if err:
            errs.append("%s: %s" % (rv[0], err))
        else:
            res[rv[0]] = a
    vals = list(res.values())
    if len(vals) == 2 and vals[0] != vals[1]:
        return vals[0], ("RESOLVERS DISAGREE - Google=%s Cloudflare=%s"
                         % (vals[0], vals[1]))
    return (vals[0] if vals else []), ("; ".join(errs) if errs else None)


# ------------------------------------------------------------------ registrar
def rdap(domain):
    try:
        r = requests.get("https://rdap.org/domain/" + domain,
                         headers={"Accept": "application/rdap+json",
                                  "User-Agent": UA},
                         timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return {"error": "RDAP HTTP %s" % r.status_code}
        d = r.json()
    except Exception as e:
        return {"error": str(e)[:120]}
    o = {"status": d.get("status"), "registry_nameservers":
         [n.get("ldhName", "").lower() for n in d.get("nameservers", [])]}
    for ev in d.get("events", []):
        o[ev.get("eventAction", "?").replace(" ", "_")] = (ev.get("eventDate") or "")[:10]
    for e in d.get("entities", []):
        v = (e.get("vcardArray") or [None, []])[1] or []
        name = next((x[3] for x in v if x and x[0] == "fn"), None)
        for role in e.get("roles", []):
            o[role] = name
    return o


# ------------------------------------------------------------------ HTTP / TLS
def fetch(url):
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT,
                         allow_redirects=True)
        return {
            "final_url": r.url,
            "status": r.status_code,
            "chain": [h.status_code for h in r.history] + [r.status_code],
            "server": r.headers.get("server"),
            "powered_by": r.headers.get("x-powered-by"),
            "cf_ray": r.headers.get("cf-ray"),
            "hsts": r.headers.get("strict-transport-security"),
            # capture any text body, not just text/html - robots.txt and
            # sitemap.xml are text/plain and application/xml
            "html": (r.text if re.match(r"text/|application/(xml|xhtml|json)",
                                        r.headers.get("content-type", ""))
                     else ""),
            "headers": {k.lower(): v for k, v in r.headers.items()},
        }
    except Exception as e:
        return {"error": str(e)[:140]}


def tls(host):
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=12) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                c = ss.getpeercert()
        issuer = dict(x[0] for x in c.get("issuer", []))
        sans = [v for k, v in c.get("subjectAltName", []) if k == "DNS"]
        exp = c.get("notAfter")
        days = None
        try:
            d = datetime.datetime.strptime(exp, "%b %d %H:%M:%S %Y %Z")
            days = (d - datetime.datetime.utcnow()).days
        except Exception:
            pass
        return {"issuer": issuer.get("organizationName") or issuer.get("commonName"),
                "expires": exp, "days_left": days, "sans": sans[:12]}
    except Exception as e:
        return {"error": str(e)[:120]}


def rdns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None


# ------------------------------------------------------------------ page facts
def page_facts(html, base):
    f = {}
    if not html:
        return f
    g = lambda rx: (re.search(rx, html, re.I | re.S) or [None, None])
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    f["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:160] if m else None
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.I)
    f["meta_description"] = m.group(1)[:220] if m else None
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
    f["og_image"] = m.group(1) if m else None
    icons = re.findall(r'<link[^>]+rel=["\'][^"\']*icon[^"\']*["\'][^>]+href=["\']([^"\']+)', html, re.I)
    f["favicons"] = list(dict.fromkeys(icons))[:4]
    logos = re.findall(r'<img[^>]+(?:class|id|alt|src)=["\'][^"\']*logo[^"\']*["\'][^>]*>', html, re.I)
    srcs = []
    for tag in logos[:6]:
        m2 = re.search(r'src=["\']([^"\']+)', tag, re.I)
        if m2:
            srcs.append(m2.group(1))
    f["logo_candidates"] = list(dict.fromkeys(srcs))[:5]
    f["h1"] = [re.sub(r"<[^>]+>", "", x).strip()[:120]
               for x in re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)][:4]
    phones = re.findall(r'tel:([+0-9()\-.\s]{7,22})', html, re.I)
    phones += re.findall(r'(?<![\d/])(\+?\d[\d\-.\s()]{8,18}\d)(?![\d/])', html)
    f["phones"] = list(dict.fromkeys(p.strip() for p in phones))[:6]
    mails = re.findall(r'mailto:([^"\'?\s>]+)', html, re.I)
    mails += re.findall(r'[\w.+-]+@[\w-]+\.[\w.]{2,12}', html)
    f["emails"] = [e for e in dict.fromkeys(mails)
                   if not e.lower().endswith((".png", ".jpg", ".webp", ".svg"))][:6]
    f["platform"] = [n for n, rx in PLATFORM if re.search(rx, html, re.I)]
    an = []
    for name, rx in ANALYTICS:
        hits = re.findall(rx, html)
        if hits:
            an.append("%s (%s)" % (name, ", ".join(dict.fromkeys(
                h if isinstance(h, str) else h[0] for h in hits))[:60]))
    f["analytics"] = an
    f["lang"] = (g(r'<html[^>]+lang=["\']([^"\']+)')[1])
    return f


# ------------------------------------------------------------------ main
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    raw = sys.argv[1].strip()
    domain = re.sub(r"^https?://", "", raw).split("/")[0].lstrip("www.").lower()
    outdir = os.path.abspath(sys.argv[sys.argv.index("--out") + 1]
                             if "--out" in sys.argv else "recon-" + domain)
    os.makedirs(outdir, exist_ok=True)
    R = {"domain": domain, "checked": datetime.datetime.now().isoformat()[:16]}
    notes = []

    sys.stderr.write("registrar...\n")
    R["registrar"] = rdap(domain)

    sys.stderr.write("dns...\n")
    dns = {}
    for rtype, name in [("NS", domain), ("A", domain), ("AAAA", domain),
                        ("A", "www." + domain), ("CNAME", "www." + domain),
                        ("MX", domain), ("TXT", domain),
                        ("TXT", "_dmarc." + domain), ("CAA", domain),
                        ("TXT", "_lovable." + domain),
                        ("TXT", "_lovable-email." + domain)]:
        key = "%s %s" % (rtype, name)
        vals, note = dns_both(name, rtype)
        if vals:
            dns[key] = vals
        if note:
            notes.append("%s: %s" % (key, note))
    dkim = {}
    for sel in DKIM_SELECTORS:
        v, _ = dns_both("%s._domainkey.%s" % (sel, domain), "TXT")
        if v:
            dkim[sel] = (v[0][:80] + "...") if len(v[0]) > 80 else v[0]
    R["dns"] = dns
    R["dkim_selectors_found"] = dkim

    txt = dns.get("TXT " + domain, [])
    spf = [t for t in txt if t.lower().startswith("v=spf1")]
    R["spf"] = {"records": spf, "count": len(spf),
                "problem": "MORE THAN ONE SPF RECORD - mail will fail" if len(spf) > 1
                else (None if spf else "no SPF record")}
    dm = dns.get("TXT _dmarc." + domain, [])
    R["dmarc"] = {"record": dm[0] if dm else None,
                  "policy": (re.search(r"p=(\w+)", dm[0]).group(1) if dm and re.search(r"p=(\w+)", dm[0]) else None)}
    R["verification_txt"] = {k: v for k, v in dns.items()
                             if any(s in k for s in VERIFY_TXT)}

    sys.stderr.write("hosting...\n")
    ips = dns.get("A " + domain, [])
    R["hosting"] = {"ips": ips, "reverse_dns": {ip: rdns(ip) for ip in ips[:4]}}

    sys.stderr.write("http...\n")
    apex = fetch("https://" + domain)
    www = fetch("https://www." + domain)
    R["http"] = {"apex": {k: v for k, v in apex.items() if k != "html"},
                 "www": {k: v for k, v in www.items() if k != "html"}}
    R["hosting"]["behind_cloudflare"] = bool(apex.get("cf_ray"))

    sys.stderr.write("tls...\n")
    R["tls"] = tls(domain)

    sys.stderr.write("page...\n")
    html = apex.get("html") or www.get("html") or ""
    R["page"] = page_facts(html, domain)

    # The markup does not always name the platform. A server-rendered React
    # site can look like nothing at all, while the host it is served from says
    # exactly what it is. Reported separately so it is never mistaken for
    # something found in the page itself.
    where = " ".join([domain] + [v or "" for v in
                                 R["hosting"]["reverse_dns"].values()])
    R["page"]["platform_from_host"] = [
        n for n, rx in HOST_PLATFORM if re.search(rx, where, re.I)]

    sys.stderr.write("robots / sitemap...\n")
    rb = fetch("https://%s/robots.txt" % domain)
    R["robots"] = {"status": rb.get("status"),
                   "sitemaps": re.findall(r"(?i)sitemap:\s*(\S+)", rb.get("html", "") or "")}
    sm = fetch("https://%s/sitemap.xml" % domain)
    R["sitemap"] = {"status": sm.get("status"),
                    "url_count": len(re.findall(r"<loc>", sm.get("html", "") or ""))}
    R["notes"] = notes

    # ------------------------------------------------------------ risks
    risks = []
    reg = R["registrar"]
    regns = set(reg.get("registry_nameservers") or [])
    livens = set(n.lower() for n in dns.get("NS " + domain, []))
    if regns and livens and regns != livens:
        risks.append("Registry delegates to %s but the live NS answer is %s. "
                     "Whichever zone you edit, confirm it is the one being served."
                     % (sorted(regns), sorted(livens)))
    if R["spf"]["problem"]:
        risks.append("SPF: " + R["spf"]["problem"])
    if not R["dmarc"]["record"]:
        risks.append("No DMARC record. Mail is more likely to land in spam.")
    if not dns.get("MX " + domain):
        risks.append("No MX record - this domain receives no email, or mail is "
                     "on another domain. Confirm before any DNS change.")
    else:
        risks.append("MX is %s - this MUST survive any nameserver or zone change, "
                     "or the client's mail stops." % dns["MX " + domain])
    if R["hosting"]["behind_cloudflare"]:
        risks.append("Behind Cloudflare (proxied). The A record hides the real "
                     "origin, and an orange-cloud record breaks platform domain "
                     "binding on Lovable/Vercel-style hosts.")
    exp = reg.get("expiration")
    if exp:
        try:
            left = (datetime.datetime.strptime(exp, "%Y-%m-%d") - datetime.datetime.now()).days
            if left < 90:
                risks.append("Domain expires in %d days (%s)." % (left, exp))
        except Exception:
            pass
    d = (R["tls"] or {}).get("days_left")
    if isinstance(d, int) and d < 21:
        risks.append("TLS certificate expires in %d days." % d)
    og = (R["page"] or {}).get("og_image") or ""
    if og and domain not in og:
        risks.append("OG image is served from '%s', not this domain - a staging "
                     "or preview URL has leaked into production metadata."
                     % og.split("/")[2] if "//" in og else og)
    if R["sitemap"]["status"] == 200 and R["sitemap"]["url_count"] == 0:
        risks.append("sitemap.xml returns 200 but contains no <loc> entries.")
    if not R["robots"]["sitemaps"]:
        risks.append("robots.txt does not declare a sitemap.")
    reg_name = reg.get("registrant") or reg.get("registrar")
    if reg_name:
        risks.append("Registrant/registrar of record is '%s'. Confirm the CLIENT "
                     "owns the domain - an agency named here means they do not."
                     % reg_name)
    R["risks"] = risks

    # ------------------------------------------------------------ report
    L = ["# Site recon - %s" % domain, "",
         "Checked %s. Everything below was read from public sources; nothing "
         "needed a login." % R["checked"], ""]

    L += ["## Domain", ""]
    for k in ("registrar", "registrant", "status", "registration", "expiration",
              "last_changed", "registry_nameservers"):
        if reg.get(k) is not None:
            L.append("- **%s:** %s" % (k.replace("_", " "), reg[k]))
    if reg.get("error"):
        L.append("- RDAP lookup failed: %s" % reg["error"])
    L.append("")

    L += ["## DNS (asked Google and Cloudflare separately)", "",
          "| Record | Value |", "|---|---|"]
    for k, v in dns.items():
        L.append("| `%s` | %s |" % (k, "<br>".join("`%s`" % x[:120] for x in v)))
    L.append("")
    if dkim:
        L += ["DKIM selectors that exist: " + ", ".join("`%s`" % s for s in dkim), ""]

    L += ["## Hosting", "",
          "- **IPs:** %s" % (ips or "none"),
          "- **Reverse DNS:** %s" % R["hosting"]["reverse_dns"],
          "- **Behind Cloudflare:** %s" % R["hosting"]["behind_cloudflare"],
          "- **Server header:** %s" % apex.get("server"),
          "- **TLS:** %s, expires %s (%s days)" % (R["tls"].get("issuer"),
                                                   R["tls"].get("expires"),
                                                   R["tls"].get("days_left")), ""]

    L += ["## Site", "",
          "- **apex:** HTTP %s via %s -> %s" % (apex.get("status"), apex.get("chain"), apex.get("final_url")),
          "- **www:** HTTP %s -> %s" % (www.get("status"), www.get("final_url")), ""]
    p = R["page"]
    for k, label in [("platform", "Platform / CMS"),
                     ("platform_from_host", "Platform (from the host, not the page)"),
                     ("analytics", "Analytics"),
                     ("title", "Title"), ("meta_description", "Meta description"),
                     ("h1", "H1"), ("lang", "lang"), ("favicons", "Favicon"),
                     ("logo_candidates", "Logo"), ("og_image", "OG image"),
                     ("phones", "Phone"), ("emails", "Email")]:
        if p.get(k):
            L.append("- **%s:** %s" % (label, p[k]))
    L += ["", "- **robots.txt:** HTTP %s, declares %s" % (R["robots"]["status"], R["robots"]["sitemaps"] or "no sitemap"),
          "- **sitemap.xml:** HTTP %s, %d URLs" % (R["sitemap"]["status"], R["sitemap"]["url_count"]), ""]

    L += ["## Risks and things to confirm", ""]
    for r in risks:
        L.append("- " + r)
    if notes:
        L += ["", "### Lookup notes", ""] + ["- " + n for n in notes]

    L += ["", "## What still has to come from the client", "",
          "These cannot be discovered from outside. Ask for them before any "
          "migration or go-live:", "",
          "- Registrar login, or the auth/EPP code and the domain unlocked",
          "- DNS panel login (and which panel is authoritative, not just which exists)",
          "- Hosting / CMS admin login, and SFTP or Git access",
          "- Email: who hosts the mailboxes, and the admin for them",
          "- Analytics, Search Console, Tag Manager and Ads access",
          "- Logo source files, brand colours and fonts, licences for any stock imagery",
          "- The legal entity name, address, phone and licence numbers for the footer",
          "- Which pages must keep their URL, and which may be retired",
          "- Who signs off, and who may never be surprised by a change", ""]

    md = "\n".join(L)
    open(os.path.join(outdir, "recon.md"), "w", encoding="utf-8", newline="\n").write(md)
    open(os.path.join(outdir, "recon.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(R, indent=1, ensure_ascii=False))
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)
    sys.stderr.write("\nwritten: %s\n" % os.path.join(outdir, "recon.md"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
