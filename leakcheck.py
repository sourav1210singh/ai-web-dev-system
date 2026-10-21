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
           "hero", "river", "mount", "studio", "group", "media", "design"}

SECRETS = [
    ("credential", re.compile(
        r"(?i)\b(api[_-]?key|secret|token|passwd|password|client[_-]?secret)\b"
        r"\s*[=:]\s*['\"]?[A-Za-z0-9_\-\.]{16,}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.]{20,}")),
    ("supabase ref", re.compile(r"\b[a-z]{20}\.supabase\.co")),
    ("public IPv4", re.compile(
        r"\b(?!10\.|127\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|0\.)"
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
        for w in re.split(r"[^A-Za-z0-9]+", name):
            if len(w) > 3 and w.lower() not in GENERIC:
                terms.add(w.lower())
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
    terms -= {"claude", "github", "google", "lovable", "supabase", "vercel",
              "npmjs", "anthropic", "schema", "wordpress", "example",
              "cloudflare", "microsoft", "typekit", "gravatar", "linkedin"}
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

    hits = []
    for p in files():
        rel = os.path.relpath(p, HERE)
        try:
            text = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            low = line.lower()
            for t in terms:
                if re.search(r"\b%s\b" % re.escape(t), low):
                    hits.append(("client name '%s'" % t, rel, i, line.strip()[:90]))
            for label, rx in SECRETS:
                m = rx.search(line)
                if m:
                    hits.append((label, rel, i, line.strip()[:90]))

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
