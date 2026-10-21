# -*- coding: utf-8 -*-
"""Element-by-element parity between an old page and its replacement.

    python parity.py <old> <new> [--out DIR] [--quiet]
    python parity.py --map pairs.txt [--out DIR]

<old> and <new> are each a URL or a path to a saved HTML file. A saved file is
how you check a page that renders client-side: capture the RENDERED html from
the browser, not the server response, or every React build looks empty.

pairs.txt holds one "old-url<TAB>new-url" per line, # for a comment.

It compares what a person would compare: headings, body text, links, images and
their alt text, phone numbers, email addresses, forms, structured data, title,
meta description and canonical. Anything on the old page and not on the new one
is reported.

Exit codes:  0 nothing missing   1 something missing or uncheckable   2 usage
"""
import difflib, io, os, re, sys, unicodedata
from urllib.parse import urljoin, urlparse

try:
    import requests
except ImportError:
    print("needs requests:  pip install requests")
    sys.exit(2)
try:
    import lxml.html as LH
except ImportError:
    print("needs lxml:  pip install lxml")
    sys.exit(2)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
GOOGLEBOT = ("Mozilla/5.0 (compatible; Googlebot/2.1; "
             "+http://www.google.com/bot.html)")
T = 25
FUZZ = 0.86          # two texts this close are the same sentence, reworded
MIN_WORDS = 3        # shorter than this is a label; compared as a link instead
SHELL_WORDS = 60     # below this the html is a shell and nothing rendered


# --- fetching ----------------------------------------------------------
class Resp(object):
    def __init__(self, status, text):
        self.status_code = status
        self.text = text


def curl(url):
    """Three identities before concluding anything.

    A WAF that refuses a browser user agent coming from a non-browser client
    will often serve curl's own UA and Googlebot perfectly well. Measured on a
    live client site: fake Chrome 403, default curl 200, Googlebot 200.
    """
    import subprocess, tempfile
    last = None
    for extra in ([["-A", UA], [], ["-A", GOOGLEBOT]]):
        fd, tmp = tempfile.mkstemp()
        os.close(fd)
        try:
            p = subprocess.run(
                ["curl", "-sSL", "--max-time", str(T)] + extra +
                ["-o", tmp, "-w", "%{http_code}", url],
                capture_output=True, text=True, timeout=T + 10)
            body = io.open(tmp, "rb").read().decode("utf-8", "replace")
            last = Resp(int((p.stdout or "0").strip() or 0), body)
            if last.status_code == 200:
                return last
        except Exception:
            pass
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass
    return last


def fetch(target):
    """A URL or a local file. Returns (html, note); html is None on failure."""
    if os.path.isfile(target):
        return io.open(target, encoding="utf-8",
                       errors="replace").read(), "saved file"
    if not re.match(r"(?i)^https?://", target):
        target = "https://" + target
    r = None
    try:
        r = requests.get(target, headers={"User-Agent": UA}, timeout=T,
                         allow_redirects=True)
    except Exception:
        r = None
    if r is None or r.status_code in (401, 403, 406, 429, 503):
        alt = curl(target)
        if alt is not None and alt.status_code == 200:
            return alt.text, "fetched via curl fallback"
        r = r or alt
    if r is None:
        return None, "could not be fetched (connection failed)"
    if r.status_code != 200:
        if r.status_code in (401, 403, 406, 429, 503):
            return None, ("BLOCKED - HTTP %d for us. The page may well exist; "
                          "this host refuses our requests." % r.status_code)
        return None, "HTTP %d" % r.status_code
    return r.text, "HTTP 200"


# --- reading a page ----------------------------------------------------
def norm(s):
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace(" ", " ").replace("​", "")
    s = re.sub(r"[‐-―]", "-", s)
    s = re.sub(r"[‘’]", "'", s)
    s = re.sub(r"[“”]", '"', s)
    return re.sub(r"\s+", " ", s).strip()


def key(s):
    return re.sub(r"[^a-z0-9 ]+", "", norm(s).lower()).strip()


EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_CAND = re.compile(r"\+?\d[\d\s().-]{7,}\d")
BLOCKS = ("p", "li", "td", "th", "blockquote", "figcaption", "dd", "dt",
          "h1", "h2", "h3", "h4", "h5", "h6")


def digits(s):
    return re.sub(r"\D", "", s)


def phones(text):
    """Last ten digits, so +1 / 001 / spaced forms all compare equal."""
    out = set()
    for cand in PHONE_CAND.findall(text):
        d = digits(cand)
        if 10 <= len(d) <= 15:
            out.add(d[-10:])
    return out


def block_units(node):
    """Every block of real text under this node, de-duplicated, in order."""
    seen, units = set(), []
    for el in node.xpath("|".join(".//" + b for b in BLOCKS)):
        txt = norm(el.text_content())
        if len(txt.split()) < MIN_WORDS:
            continue
        k = key(txt)
        if k and k not in seen:
            seen.add(k)
            units.append(txt)
    return units


def read(html, base):
    """Everything on the page a client would notice if it went missing."""
    doc = LH.fromstring(html)
    for bad in doc.xpath("//script|//style|//noscript|//template"):
        bad.getparent().remove(bad)

    o = {"_base": base}
    t = doc.xpath("//title/text()")
    o["title"] = norm(t[0]) if t else ""
    md = doc.xpath("//meta[@name='description']/@content")
    o["meta"] = norm(md[0]) if md else ""
    cn = doc.xpath("//link[@rel='canonical']/@href")
    o["canonical"] = norm(cn[0]) if cn else ""

    o["headings"] = []
    for lvl in range(1, 7):
        for el in doc.xpath("//h%d" % lvl):
            txt = norm(el.text_content())
            if txt:
                o["headings"].append((lvl, txt))

    o["units"] = block_units(doc)

    links = {}
    for el in doc.xpath("//a[@href]"):
        href = (el.get("href") or "").strip()
        if href.startswith("#") or href.lower().startswith("javascript:"):
            continue
        label = norm(el.text_content()) or norm(el.get("aria-label") or "")
        links[urljoin(base, href)] = label
    o["links"] = links

    o["images"] = []
    for el in doc.xpath("//img"):
        src = el.get("src") or el.get("data-src") or ""
        o["images"].append((os.path.basename(urlparse(src).path),
                            norm(el.get("alt") or "")))

    o["forms"] = []
    for f in doc.xpath("//form"):
        names = [n for n in f.xpath(".//input/@name|.//select/@name|"
                                    ".//textarea/@name") if n]
        o["forms"].append(sorted(set(names)))

    body = norm(doc.text_content())
    o["words"] = len(body.split())
    o["emails"] = set(e.lower() for e in EMAIL.findall(body))
    o["phones"] = phones(body)
    for h in doc.xpath("//a[starts-with(@href,'tel:')]/@href"):
        d = digits(h)
        if 10 <= len(d) <= 15:
            o["phones"].add(d[-10:])
    for h in doc.xpath("//a[starts-with(@href,'mailto:')]/@href"):
        o["emails"].add(h[7:].split("?")[0].strip().lower())

    o["jsonld"] = sorted(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', html)))

    # Coverage over the whole page is diluted by the nav and the footer, which
    # match on every page of the site. A page can lose half its real content
    # and still score high, so measure the main content on its own. This
    # mutates the tree, which is why it is last.
    scope = (doc.xpath("//main") or doc.xpath("//article") or
             doc.xpath("//*[@role='main']"))
    if scope:
        scope = scope[0]
    else:
        for chrome in doc.xpath("//nav|//header|//footer|//aside"):
            chrome.getparent().remove(chrome)
        scope = doc
    o["main_units"] = block_units(scope)
    return o


# --- comparing ---------------------------------------------------------
def missing(old_items, new_items):
    """Old items with no counterpart on the new page, exact or reworded.

    Each new item can account for ONE old item. Without that, eight similar
    paragraphs on the old page all match the four that survived and the loss
    reads as nothing missing - which is the failure this whole script exists
    to catch.
    """
    pool = [k for k in (key(x) for x in new_items) if k]
    gone = []
    for item in old_items:
        k = key(item)
        if not k:
            continue
        if k in pool:
            pool.remove(k)
            continue
        m = difflib.get_close_matches(k, pool, n=1, cutoff=FUZZ)
        if m:
            pool.remove(m[0])
            continue
        gone.append(item)
    return gone


def path_of(u):
    return urlparse(u).path.rstrip("/") or "/"


def compare(old, new):
    """Returns (blockers, warnings, notes), each a list of strings."""
    B, W, N = [], [], []

    for h in missing([x[1] for x in old["headings"]],
                     [x[1] for x in new["headings"]]):
        B.append("heading missing: %s" % h[:110])

    gone_u = missing(old["units"], new["units"])
    kept = len(old["units"]) - len(gone_u)
    cover = (float(kept) / len(old["units"])) if old["units"] else 1.0
    N.append("whole page: %d of %d text blocks carried over (%.0f%%), nav and "
             "footer included" % (kept, len(old["units"]), cover * 100))

    # the number that decides, measured on the main content alone
    gone_m = missing(old["main_units"], new["main_units"])
    kept_m = len(old["main_units"]) - len(gone_m)
    cover_m = (float(kept_m) / len(old["main_units"])) \
        if old["main_units"] else cover
    N.append("main content: %d of %d text blocks carried over (%.0f%%)"
             % (kept_m, len(old["main_units"]), cover_m * 100))
    if cover_m < 0.9:
        B.append("main content coverage %.0f%% - %d text blocks from the old "
                 "page are not on the new one" % (cover_m * 100, len(gone_m)))
    for u in gone_u[:25]:
        W.append("text block missing: %s" % u[:140])
    if len(gone_u) > 25:
        W.append("... and %d more text blocks" % (len(gone_u) - 25))

    for p in sorted(old["phones"] - new["phones"]):
        B.append("phone number missing: ends %s" % p[-4:])
    for e in sorted(old["emails"] - new["emails"]):
        B.append("email address missing: %s" % e)

    old_host = urlparse(old["_base"]).netloc
    new_keys = set(urlparse(u).netloc + path_of(u) for u in new["links"])
    for u in sorted(old["links"]):
        host = urlparse(u).netloc
        if not host or host == old_host:
            continue
        if host + path_of(u) not in new_keys:
            W.append("outbound link missing: %s  (%s)"
                     % (u, old["links"][u] or "-"))

    old_paths = set(path_of(u) for u in old["links"]
                    if urlparse(u).netloc == old_host)
    new_paths = set(path_of(u) for u in new["links"])
    for p in sorted(old_paths - new_paths):
        W.append("internal link not on the new page: %s" % p)

    old_alt = [a for _s, a in old["images"] if a]
    new_alt = [a for _s, a in new["images"] if a]
    for a in missing(old_alt, new_alt)[:15]:
        W.append("image alt text missing: %s" % a[:110])
    N.append("images: %d old, %d new (%d with alt -> %d with alt)"
             % (len(old["images"]), len(new["images"]), len(old_alt),
                len(new_alt)))
    if len(new["images"]) < len(old["images"]):
        W.append("%d fewer images on the new page"
                 % (len(old["images"]) - len(new["images"])))

    if len(new["forms"]) < len(old["forms"]):
        B.append("form missing: the old page had %d, the new one has %d"
                 % (len(old["forms"]), len(new["forms"])))
    else:
        for i, fields in enumerate(old["forms"]):
            lost = sorted(set(fields) - set(new["forms"][i]))
            if lost:
                W.append("form %d lost fields: %s" % (i + 1, ", ".join(lost)))

    if not new["title"]:
        B.append("the new page has no <title>")
    if old["meta"] and not new["meta"]:
        W.append("meta description missing on the new page")
    if old["jsonld"] and not new["jsonld"]:
        W.append("structured data missing (the old page had: %s)"
                 % ", ".join(old["jsonld"][:6]))
    N.append("words: %d old -> %d new" % (old["words"], new["words"]))
    N.append("structured data: %s -> %s"
             % (", ".join(old["jsonld"]) or "none",
                ", ".join(new["jsonld"]) or "none"))
    return B, W, N


def one(old_t, new_t):
    """Compare one pair. Returns (ok, report_lines); ok is None if it could
    not be compared at all, which is never reported as a pass."""
    L = ["## %s" % old_t, "   -> %s" % new_t, ""]
    oh, on_ = fetch(old_t)
    if oh is None:
        L.append("CANNOT COMPARE - old: %s" % on_)
        return None, L
    nh, nn = fetch(new_t)
    if nh is None:
        L.append("CANNOT COMPARE - new: %s" % nn)
        return None, L

    old = read(oh, old_t if old_t.startswith("http") else "http://old/")
    new = read(nh, new_t if new_t.startswith("http") else "http://new/")

    for label, page, note in (("old", old, on_), ("new", new, nn)):
        if page["words"] < SHELL_WORDS:
            L.append("CANNOT COMPARE - the %s page returned %d words of text "
                     "(%s). That is a client-rendered shell, not the content. "
                     "Capture the RENDERED html in the browser and pass that "
                     "file instead." % (label, page["words"], note))
            return None, L

    B, W, N = compare(old, new)
    L += ["   %s" % n for n in N]
    L.append("")
    if B:
        L.append("MISSING - fix before this goes live:")
        L += ["   - %s" % b for b in B]
        L.append("")
    if W:
        L.append("CHECK:")
        L += ["   - %s" % w for w in W]
        L.append("")
    if not B and not W:
        L.append("   Everything on the old page is accounted for.")
        L.append("")
    return (not B), L


def pairs_from(path):
    out = []
    for line in io.open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\t+|\s*\|\s*|\s{2,}", line)
        if len(parts) >= 2:
            out.append((parts[0].strip(), parts[1].strip()))
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = list(sys.argv[1:])
    out_dir = "."
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            print("--out needs a directory")
            return 2
        out_dir = args[i + 1]
        del args[i:i + 2]
    quiet = "--quiet" in args
    args = [a for a in args if a == "--map" or not a.startswith("--")]

    if args[:1] == ["--map"]:
        if len(args) < 2:
            print(__doc__)
            return 2
        todo = pairs_from(args[1])
        if not todo:
            print("no pairs found in %s" % args[1])
            return 2
    elif len(args) >= 2:
        todo = [(args[0], args[1])]
    else:
        print(__doc__)
        return 2

    lines = ["# Migration parity", ""]
    bad = unknown = 0
    for o, n in todo:
        ok, L = one(o, n)
        lines += L
        if ok is None:
            unknown += 1
        elif not ok:
            bad += 1
    lines.append("---")
    lines.append("%d compared, %d with missing content, %d could not be "
                 "compared" % (len(todo), bad, unknown))
    text = "\n".join(lines)
    if not quiet:
        print(text)
    try:
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, "parity-report.md")
        io.open(p, "w", encoding="utf-8", newline="\n").write(text + "\n")
        print("\nreport: %s" % p)
    except Exception as e:
        print("\ncould not write the report: %s" % e)
    return 1 if (bad or unknown) else 0


if __name__ == "__main__":
    sys.exit(main())
