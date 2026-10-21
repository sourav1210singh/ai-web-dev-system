# -*- coding: utf-8 -*-
"""Check the three files a site is usually missing, plus the favicon.

    python check.py <domain> [<domain> ...]

For each domain: /favicon.ico (and whether it is still the platform default),
/robots.txt (and whether its Sitemap line points at the real domain),
/llms.txt, /sitemap.xml, and whether og:image is served from the real domain.
"""
import hashlib, re, sys

try:
    import requests
except ImportError:
    print("needs requests:  pip install requests")
    sys.exit(2)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
T = 20
# the Lovable starter favicon, by size. Confirmed against a fresh project.
PLATFORM_HINT = re.compile(r"(?i)lovable|gpteng|vercel|netlify|vite")


class Resp(object):
    """Minimal response, so a curl fallback looks like a requests response."""
    def __init__(self, status, body, ctype=""):
        self.status_code = status
        self.content = body
        self.headers = {"content-type": ctype}
        try:
            self.text = body.decode("utf-8", "replace")
        except Exception:
            self.text = ""


GOOGLEBOT = ("Mozilla/5.0 (compatible; Googlebot/2.1; "
             "+http://www.google.com/bot.html)")


def curl(url):
    """Try curl with several identities before concluding anything.

    Some WAFs refuse a browser user agent coming from a non-browser client
    while serving curl's own UA and Googlebot perfectly well. Measured on a
    live client site: fake Chrome UA 403, default curl UA 200, Googlebot 200.
    A refusal for one identity says nothing about whether the file exists.
    """
    import subprocess, tempfile, os
    attempts = [["-A", UA], [], ["-A", GOOGLEBOT]]
    last = None
    for extra in attempts:
        fd, tmp = tempfile.mkstemp()
        os.close(fd)
        try:
            p = subprocess.run(
                ["curl", "-sSL", "--max-time", str(T)] + extra +
                ["-o", tmp, "-w", "%{http_code}\t%{content_type}", url],
                capture_output=True, text=True, timeout=T + 10)
            code, _, ctype = (p.stdout or "0\t").partition("\t")
            r = Resp(int(code or 0), open(tmp, "rb").read(), ctype)
            last = r
            if r.status_code == 200:
                return r
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass
    return last


def get(url, binary=False):
    r = None
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=T,
                         allow_redirects=True)
    except Exception:
        r = None
    # blocked or failed for us: ask curl before concluding anything
    if r is None or r.status_code in (401, 403, 406, 429, 503):
        alt = curl(url)
        if alt is not None and alt.status_code == 200:
            return alt
        if r is None:
            return alt
    return r


def _why(r):
    """Say what actually happened. A refusal is not a missing file."""
    if r is None:
        return "could not be fetched (connection failed)"
    c = r.status_code
    if c in (401, 403, 406, 429, 503):
        return ("BLOCKED - HTTP %d for us. The file may well exist; this host "
                "refuses our requests. Check in a browser." % c)
    if c == 404:
        return "MISSING (404)"
    return "unexpected HTTP %d" % c


def row(domain):
    base = "https://" + domain.strip().strip("/")
    o = {"domain": domain}

    fav = get(base + "/favicon.ico")
    if fav is None or fav.status_code != 200:
        o["favicon"] = _why(fav)
    else:
        body = fav.content
        o["favicon"] = "%d bytes, %s, md5 %s" % (
            len(body), fav.headers.get("content-type", "?"),
            hashlib.md5(body).hexdigest()[:8])

    rb = get(base + "/robots.txt")
    if rb is None or rb.status_code != 200:
        o["robots"] = _why(rb)
    elif "<html" in rb.text[:400].lower():
        o["robots"] = "NOT A FILE - the site returned HTML"
    else:
        sm = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rb.text)
        bad = [s for s in sm if domain.replace("www.", "") not in s]
        o["robots"] = "ok, sitemap: %s%s" % (
            sm or "NOT DECLARED",
            "  <-- WRONG DOMAIN" if bad else "")

    lm = get(base + "/llms.txt")
    if lm is None or lm.status_code != 200:
        o["llms"] = _why(lm)
    elif "<html" in lm.text[:400].lower():
        o["llms"] = "NOT A FILE - the site returned HTML"
    else:
        links = re.findall(r"https?://([a-z0-9.-]+)", lm.text, re.I)
        wrong = sorted({h for h in links
                        if domain.replace("www.", "") not in h})
        o["llms"] = "ok, %d lines%s" % (
            len(lm.text.splitlines()),
            ("  <-- links to " + ", ".join(wrong[:3])) if wrong else "")

    sm2 = get(base + "/sitemap.xml")
    if sm2 is None or sm2.status_code != 200:
        o["sitemap"] = _why(sm2)
    else:
        o["sitemap"] = "%d URLs" % len(re.findall(r"<loc>", sm2.text))

    home = get(base + "/")
    o["og_image"] = "-"
    if home is not None and home.status_code == 200:
        m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                      home.text, re.I)
        if m:
            u = m.group(1)
            o["og_image"] = u if domain.replace("www.", "") in u else (
                u + "  <-- WRONG DOMAIN")
        else:
            o["og_image"] = "not set"
    return o


def main():
    doms = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not doms:
        print(__doc__)
        return 2
    sys.stdout.reconfigure(encoding="utf-8")
    for d in doms:
        o = row(d)
        print("\n### %s" % d)
        for k in ("favicon", "robots", "llms", "sitemap", "og_image"):
            print("  %-10s %s" % (k, o[k]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
