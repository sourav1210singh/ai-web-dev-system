# -*- coding: utf-8 -*-
"""Is this folder safe to publish?

    python leakcheck.py            scan everything that would be pushed
    python leakcheck.py --list     show the client names it checks for

Reads the client folder names and their live domains straight off this machine,
so the list stays current without being hard-coded, then checks every file in
this folder for them, plus credentials, keys, personal paths and IP addresses.

Exit 1 if anything is found. Nothing is changed.
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Claude-Code"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", "dist"}
SKIP_FILES = {"leakcheck.py", "leakcheck-report.txt"}
TEXT = (".md", ".py", ".js", ".json", ".txt", ".yml", ".yaml", ".cmd", ".sh",
        # anything else text that could carry a domain, an address or a key
        ".html", ".htm", ".css", ".ts", ".tsx", ".jsx", ".mjs", ".cjs",
        ".toml", ".ini", ".xml", ".svg", ".env", ".sql", ".ps1", ".log")

# words that are generic even though they appear in a folder name
GENERIC = {"all", "check", "extra", "use", "water", "green", "environment",
           "business", "company", "website", "image", "electric", "llc",
           "process", "solution", "dance", "park", "garage", "portfolios",
           "thriver", "mitigation", "salesforce", "trucking", "lp",
           # ordinary English words that happen to be in a folder name
           "hero", "river", "mount", "studio", "group", "media", "design",
           "dashboard", "portal", "admin", "client", "project", "system",
           "template", "demo", "test", "site", "sites", "page", "pages"}

# Tools and platforms, which are not clients even though their domains turn up
# in the project memories. A note saying a client's site is on Webflow puts
# webflow.com in a memory file, the domain scan reads it as a client domain,
# and then every skill that names the platform - which they have to, to say how
# to work on it - reads as a leak. Naming a platform is not naming a client.
PLATFORMS = {
    "claude", "anthropic", "github", "google", "microsoft", "cloudflare",
    "lovable", "supabase", "vercel", "netlify", "npmjs", "schema", "example",
    "wordpress", "webflow", "squarespace", "shopify", "framer", "elementor",
    "figma", "typekit", "gravatar", "linkedin", "playwright", "tailwind",
    "hubspot", "mailchimp", "notion", "airtable", "screamingfrog", "semrush",
    # Analytics and ads vendors. A recon report records a client's measurement
    # IDs, which puts these domains in that project's memory, and then every
    # skill that has to name the collector to check it reads as a leak.
    "googletagmanager", "googleadservices", "doubleclick", "facebook",
    "hotjar", "clarity", "tiktok", "pinterest", "segment", "plausible",
    "usefathom", "licdn", "pinimg", "redditmedia", "analytics",
}

SECRETS = [
    ("credential", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|passwd|password|client[_-]?secret)\b"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9_\-\.]{16,}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]{20,}")),
    ("supabase ref", re.compile(r"\b[a-z]{20}\.supabase\.co")),
    # Private ranges are skipped, and so are the ranges reserved for
    # documentation: 192.0.2.0/24, 198.51.100.0/24 and 203.0.113.0/24 are
    # TEST-NET-1 to 3 under RFC 5737, and 169.254.0.0/16 is link-local. None
    # of them can belong to a client, the same reason .test and .example are
    # exempt from the email pattern below, and a fixture that needs an address
    # should be using one of these rather than inventing a real one.
    ("public IPv4", re.compile(
        r"\b(?!10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\."
        r"|192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|169\.254\.)"
        r"(\d{1,3}\.){3}\d{1,3}\b")),
    ("home path", re.compile(r"(?i)C:\\Users\\(?!<)[A-Za-z0-9._-]+\\")),
    ("personal email", re.compile(
        r"(?i)(?<![\w.+-])(?!git@|noreply@|hello@|info@)"
        r"[\w.+-]+@(?!example\.|yourdomain|github\.com|site\.com)"
        # .test .example .invalid .localhost are reserved by RFC 2606 and can
        # never belong to a client, so a fixture may use them freely
        r"(?![\w.-]*\.(?:test|example|invalid|localhost)\b)"
        r"[\w-]+\.[\w.]{2,12}\b")),
]


def client_terms():
    """Folder names and live domains found on this machine."""
    terms = set()
    for name in os.listdir(ROOT):
        p = os.path.join(ROOT, name)
        if not os.path.isdir(p) or name.startswith("."):
            continue
        words = [w for w in re.split(r"[^A-Za-z0-9]+", name) if w]
        if len(words) > 1:
            # A folder called "Beyond Border Marketing" is three ordinary
            # English words, and taking them separately flagged "border-box"
            # in a stylesheet. What identifies that client is the whole name,
            # so match the phrase and the joined form, not the pieces. Real
            # leaks of a multi-word client arrive as the full name or as a
            # domain, and the domains below cover the second case.
            joined = "".join(words).lower()
            spaced = " ".join(words).lower()
            if joined not in GENERIC:
                terms.add(joined)
                terms.add(spaced)
        elif words and len(words[0]) > 3 and words[0].lower() not in GENERIC:
            terms.add(words[0].lower())
    # domains mentioned in any project's memory
    for dp, dn, fn in os.walk(ROOT):
        if os.path.basename(dp) != "memory":
            continue
        for f in fn:
            try:
                t = io.open(os.path.join(dp, f), encoding="utf-8",
                            errors="replace").read()
            except Exception:
                continue
            # Only a real URL or a www. form counts. Without that, a sentence
            # ending "...the hero. In fact" reads as the domain "hero.in".
            for d in re.findall(
                    r"(?:https?://|www\.)([a-z0-9][a-z0-9-]{3,})\."
                    r"(?:com|in|ae|org|net|de|co|global|app|dev)\b", t, re.I):
                if d.lower() not in GENERIC and len(d) > 4:
                    terms.add(d.lower())
    terms -= PLATFORMS
    return sorted(terms)


def ignored():
    """The .gitignore patterns, so this checks what would actually ship.

    Scanning files that are never published produces failures nobody can act
    on - a local log full of personal paths is not a leak if git will not
    carry it - and a check that cries wolf is a check that gets skipped.
    """
    pats, p = [], os.path.join(HERE, ".gitignore")
    if os.path.isfile(p):
        for line in io.open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                pats.append(line.rstrip("/"))
    return pats


def is_ignored(rel, pats):
    import fnmatch
    parts = rel.replace("\\", "/").split("/")
    for pat in pats:
        if any(fnmatch.fnmatch(seg, pat) for seg in parts):
            return True
        if fnmatch.fnmatch(rel.replace("\\", "/"), pat):
            return True
    return False


def files():
    pats = ignored()
    for dp, dn, fn in os.walk(HERE):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if f in SKIP_FILES:
                continue
            if not f.lower().endswith(TEXT):
                continue
            full = os.path.join(dp, f)
            if is_ignored(os.path.relpath(full, HERE), pats):
                continue
            yield full


def main():
    terms = client_terms()
    sys.stdout.reconfigure(encoding="utf-8")
    if "--list" in sys.argv:
        print("%d terms checked:\n  %s" % (len(terms), ", ".join(terms)))
        return 0

    # Compile each term once, not once per line per file. Built inside the
    # loop this rebuilt and re-looked-up the pattern for every line of every
    # file against every term - 74 files by 60 terms - and the check went from
    # seconds to minutes as the client list grew, which is how a pre-push
    # check stops being run.
    # A stored space matches any run of whitespace, so a client name wrapped
    # across two lines is still caught.
    compiled = [(t, re.compile(r"\b%s\b" % re.escape(t)
                               .replace(r"\ ", r"\s+").replace(" ", r"\s+")))
                for t in terms]

    hits = []
    for p in files():
        rel = os.path.relpath(p, HERE)
        try:
            text = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            for t, rx in compiled:
                if rx.search(low):
                    hits.append(("client name '%s'" % t, rel, i, line.strip()[:90]))
            for label, rx in SECRETS:
                m = rx.search(line)
                if m:
                    hits.append((label, rel, i, line.strip()[:90]))

        # A client name written across a line break is invisible to a
        # line-by-line scan however flexible the pattern is, and prose wraps.
        # Multi-word terms therefore get one pass over the whole file.
        low_all = text.lower()
        for t in terms:
            if " " not in t:
                continue
            pat = r"\b%s\b" % re.escape(t).replace(r"\ ", r"\s+")
            m = re.search(pat, low_all)
            if not m:
                continue
            line_no = low_all.count("\n", 0, m.start()) + 1
            if any(h[0] == "client name '%s'" % t and h[1] == rel for h in hits):
                continue                      # already reported on one line
            hits.append(("client name '%s'" % t, rel, line_no,
                         " ".join(text[m.start():m.end() + 40].split())[:90]))

    print("# Leak check - %s\n" % HERE)
    print("checked %d file(s) against %d client term(s)\n"
          % (len(list(files())), len(terms)))
    if not hits:
        print("CLEAN. Nothing client-identifying, no credentials, no personal paths.")
        return 0
    seen = set()
    for kind, rel, ln, snip in hits:
        k = (kind, rel, ln)
        if k in seen:
            continue
        seen.add(k)
        print("  %-22s %s:%d" % (kind, rel, ln))
        print("      %s" % snip)
    print("\n%d finding(s). Fix before publishing." % len(seen))
    return 1


if __name__ == "__main__":
    sys.exit(main())
