# -*- coding: utf-8 -*-
"""Does the scaffold actually pass this system's own gates?

A starter template that claims to meet the standards and is never measured
against them is a claim, which is the thing this whole system exists to stop.
So this generates a site, serves it, and runs the real passes - `seo.js`,
`a11y.js` and `security.js` - against the output. No blockers allowed.

If a standard changes and the scaffold stops meeting it, this fails. That is
the point of it.

    python scaffoldtest.py
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import scaffold as S  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:150] + "]") if extra else ""))


class Handler(SimpleHTTPRequestHandler):
    """A real 404 for anything missing, because a soft 404 is a finding."""

    def log_message(self, *a):
        pass

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            idx = os.path.join(path, "index.html")
            if not os.path.isfile(idx):
                self.send_error(404, "Not found")
                return None
        elif not os.path.isfile(path):
            self.send_error(404, "Not found")
            return None
        return SimpleHTTPRequestHandler.send_head(self)


def serve(root):
    srv = ThreadingHTTPServer(("127.0.0.1", 0),
                              partial(Handler, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def run_node(tool, url, out, extra=None):
    p = subprocess.run(["node", os.path.join(SKILLS, tool), url, "--out", out]
                       + (extra or []), capture_output=True, text=True,
                       timeout=900)
    return p


tmp = tempfile.mkdtemp(prefix="scaffoldtest-")
try:
    site = os.path.join(tmp, "site")
    files = S.build(site, "Bright Works", "brightworks.test")
    HOST = "brightworks.test"

    # ------------------------------------------------- what it wrote
    for f in ("index.html", "contact.html", "404.html", "assets/site.css",
              "assets/site.js", "robots.txt", "sitemap.xml", "llms.txt",
              "_headers", "vercel.json", "README.md"):
        ok("it writes %s" % f, os.path.isfile(os.path.join(site, f)))

    html = io.open(os.path.join(site, "index.html"), encoding="utf-8").read()
    contact = io.open(os.path.join(site, "contact.html"), encoding="utf-8").read()
    cssrc = io.open(os.path.join(site, "assets/site.css"), encoding="utf-8").read()
    jsrc = io.open(os.path.join(site, "assets/site.js"), encoding="utf-8").read()

    # --------------------------------- the house rules, checked directly
    allsrc = html + contact + cssrc + jsrc + io.open(
        os.path.join(site, "llms.txt"), encoding="utf-8").read()
    ok("no em or en dash anywhere in the output, as character or entity",
       not S.DASHES.search(allsrc),
       "the rule has been asked for on 12 projects")

    title = re.search(r"<title>(.*?)</title>", html).group(1)
    desc = re.search(r'name="description" content="([^"]+)"', html).group(1)
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    ok("the title is inside 60 characters", len(title) <= 60, "%d: %s" % (len(title), title))
    ok("the meta description is in the 150 to 160 band",
       150 <= len(desc) <= 160, "%d chars" % len(desc))
    ok("there is exactly one h1", len(h1s) == 1, len(h1s))
    ok("the h1 is inside 60 characters", len(h1s[0]) <= 60, len(h1s[0]))
    ok("each page has its own title",
       title != re.search(r"<title>(.*?)</title>", contact).group(1))
    ok("each page has its own description",
       desc != re.search(r'name="description" content="([^"]+)"', contact).group(1),
       "duplicate descriptions are a finding")

    ok("the canonical is present", 'rel="canonical"' in html)
    ok("the lang attribute is set", '<html lang="en">' in html)
    ok("Open Graph and Twitter cards are both shipped",
       'property="og:image"' in html and 'name="twitter:card"' in html)
    ok("JSON-LD is in the served HTML, not injected later",
       'type="application/ld+json"' in html)

    ld = json.loads(re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))
    nodes = ld["@graph"]
    ids = {n.get("@id") for n in nodes if n.get("@id")}
    refs = {n["publisher"]["@id"] for n in nodes if isinstance(n.get("publisher"), dict)}
    ok("the JSON-LD parses", isinstance(nodes, list) and len(nodes) >= 2)
    ok("every @id reference resolves to a node that exists",
       refs <= ids, "refs=%s ids=%s" % (refs, ids))
    ok("the contact page carries a BreadcrumbList",
       "BreadcrumbList" in contact)
    ok("the home page does not, being the root",
       "BreadcrumbList" not in html)

    ok("the skip link points at an element that exists",
       'href="#main"' in html and 'id="main"' in html)
    ok("the landmarks are there",
       all(t in html for t in ("<header", "<nav", "<main", "<footer")))
    ok("focus is given a visible style rather than removed",
       ":focus-visible" in cssrc and "outline: none" not in cssrc,
       "outline:none with nothing put back is the commonest a11y defect")

    # -------------------------------- the measured overflow fixes
    for frag, why in ((".grid > *, .flex-row > * { min-width: 0; }",
                       "min-width:0 fixes more overflow than anything else"),
                      ("overflow-wrap: break-word", "long headings"),
                      ("hyphens: auto", "under 480px"),
                      ("overflow-wrap: anywhere", "label and value rows"),
                      ("repeat(2, minmax(0, 1fr))", "two up on a phone"),
                      ("white-space: normal", "long button text")):
        ok("the overflow fix for %s is present" % why, frag in cssrc)
    ok("the hero is sized with svh as well as vh",
       "100svh" in cssrc, "vh alone puts the CTA under the address bar")
    ok("tap targets are at least 44px", "min-height: 44px" in cssrc)

    ok("reduced motion is respected",
       "prefers-reduced-motion: no-preference" in cssrc
       and "prefers-reduced-motion: reduce" in cssrc)
    ok("the script also checks reduced motion before animating",
       "prefers-reduced-motion: reduce" in jsrc)
    # The comment saying why it is absent mentions it, so look for the
    # declaration rather than the word.
    ok("scroll-behavior smooth is never declared",
       not re.search(r"^\s*scroll-behavior\s*:", cssrc, re.M),
       "it fights a smooth-scroll library")
    ok("there is one shadow definition, not a ladder",
       cssrc.count("--shadow:") == 1 and "--shadow-lg" not in cssrc)
    ok("the base unit is stated rather than left to be inferred",
       "--unit:" in cssrc)
    ok("the type scale is six sizes",
       len(S.SCALE) == 6, ", ".join(S.SCALE))

    # ----------------------------------------------------- the form
    ok("every input has a label bound to it",
       all(('for="%s"' % i) in contact for i in ("name", "email", "phone", "job")))
    ok("autocomplete is set on the identity fields",
       'autocomplete="name"' in contact and 'autocomplete="email"' in contact)
    ok("the email field uses the email type", 'type="email"' in contact)
    ok("validation messages sit next to their field",
       'id="name-error"' in contact and 'id="email-error"' in contact)
    ok("there is a real success panel, not a toast",
       'id="sent"' in contact and "<h2>" in contact.split('id="sent"')[1][:200])
    ok("the front end does not pretend the send worked",
       "never by the front end pretending" in jsrc,
       "that is the failure this skill is about")

    # ------------------------------------------ placeholders are obvious
    ok("figures are shipped as obvious placeholders",
       "PLACEHOLDER" in html, "never an invented number")
    ok("the README says to replace them first",
       "PLACEHOLDER" in io.open(os.path.join(site, "README.md"),
                                encoding="utf-8").read())
    ok("the README says a success panel is not confirmation",
       "is not confirmation" in io.open(os.path.join(site, "README.md"),
                                        encoding="utf-8").read())

    ok("it refuses to write into a folder that already has work in it",
       subprocess.run([sys.executable, "-X", "utf8",
                       os.path.join(HERE, "scaffold.py"), site,
                       "--name", "X", "--domain", "x.test"],
                      capture_output=True, text=True).returncode == 2,
       "overwriting somebody's work is not recoverable")

    # ------------------------------------------ the gates, for real
    srv, port = serve(site)
    base = "http://127.0.0.1:%d/" % port
    # The generated absolute URLs point at the real domain, so the sitemap
    # declared in robots.txt, the canonicals and the llms.txt links all resolve
    # to a host that does not exist here. Rewriting the host is the only way to
    # exercise those for real - without it the sitemap check silently passes by
    # never reading a sitemap at all, which is how a green test says nothing.
    for root, _dirs, fs in os.walk(site):
        for f in fs:
            if not f.endswith((".html", ".txt", ".xml", ".json", ".md")):
                continue
            p = os.path.join(root, f)
            body = io.open(p, encoding="utf-8").read()
            if "https://" + HOST not in body:
                continue
            io.open(p, "w", encoding="utf-8", newline="\n").write(
                body.replace("https://" + HOST, base.rstrip("/")))
    try:
        qa = os.path.join(tmp, "qa")

        p = run_node("seo-complete/seo.js", base, os.path.join(qa, "seo"),
                     ["--pages", "3", "--max-links", "20"])
        d = json.loads(io.open(os.path.join(qa, "seo", "seo.json"),
                               encoding="utf-8").read())
        blockers = [f for f in d["findings"] if f["sev"] == "BLOCKER"]
        ok("the SEO pass finds no blockers", not blockers,
           [b["title"] for b in blockers] or "clean")
        ok("it reads a real 404 from the test server",
           not any(f["id"] == "soft-404" for f in d["findings"]))
        ok("no internal link is broken",
           (d["counts"] or {}).get("internal links broken", 1) == 0)
        ok("every page has its JSON-LD in the raw HTML",
           (d["counts"] or {}).get("pages with no JSON-LD in raw HTML", 1) == 0)
        ok("no plain-text field carries a literal entity",
           (d["counts"] or {}).get("plain-text fields with a literal entity", 1) == 0)
        ok("the site agrees with itself about its phone number",
           not any(f["id"].startswith("nap-") for f in d["findings"]),
           [f["id"] for f in d["findings"] if f["id"].startswith("nap-")])
        ok("the sitemap declared in robots.txt is actually readable",
           not any(f["id"].startswith("sitemap-") for f in d["findings"]),
           [f["id"] for f in d["findings"] if f["id"].startswith("sitemap-")])
        ok("the sitemap lists every page and none of them redirect",
           (d["sitemap"] or {}).get("count") == 2
           and not (d["sitemap"] or {}).get("redirecting"),
           d.get("sitemap"))
        ok("the title opens with the same words as the h1",
           not any(f["id"] == "title-h1-drift" for f in d["findings"]),
           "matching them is what stops Google rewriting the title")
        # Expected by design, and stated rather than hidden: a scaffold has no
        # copy yet, which client-content-audit is the skill for.
        thin = [f for f in d["findings"] if f["id"] == "thin-content"]
        ok("thin content is reported, because a scaffold has no copy",
           thin and thin[0]["sev"] == "MINOR",
           "a minor, not a blocker - the copy comes from the client")

        p = run_node("responsive-qa/a11y.js", base, os.path.join(qa, "a11y"))
        a = json.loads(io.open(os.path.join(qa, "a11y", "a11y.json"),
                               encoding="utf-8").read())
        crit = [v for row in a.get("rows", [])
                for v in (row.get("violations") or [])
                if v.get("impact") in ("critical", "serious")]
        ok("axe finds no critical or serious violation", not crit,
           [v["id"] for v in crit] or "clean")
        notes = [n for row in a.get("rows", [])
                 for n in ((row.get("sr") or {}).get("notes") or [])
                 if n.get("sev") == "MAJOR"]
        ok("the checks axe cannot make are clean too", not notes,
           [n.get("kind") for n in notes] or "clean")
        invis = [row for row in a.get("rows", [])
                 if (row.get("focus") or {}).get("invisible")]
        ok("focus is visible on every control", not invis)

        p = run_node("security-pass/security.js", base, os.path.join(qa, "sec"))
        s = json.loads(io.open(os.path.join(qa, "sec", "security.json"),
                               encoding="utf-8").read())
        sb = [f for f in s["findings"] if f["sev"] == "BLOCKER"]
        ok("the security pass finds no blockers", not sb,
           [b["title"] for b in sb] or "clean")
        ok("no secret is shipped in the output",
           not any("key" in f["id"] or "secret" in f["id"] for f in s["findings"]))
        ok("the transport checks were skipped rather than failed on localhost",
           s.get("devHost") is True)
    finally:
        srv.shutdown()
finally:
    shutil.rmtree(tmp, ignore_errors=True)

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
