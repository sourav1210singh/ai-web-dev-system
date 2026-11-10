# -*- coding: utf-8 -*-
"""A site skeleton that already passes this system's own gates.

    python scaffold.py <out-dir> --name "Business Name" --domain example.com
                       [--design <DESIGN.md>] [--kind marketing|dense]

Every other tool here measures. This one builds, and it exists because the gap
was measurable: thirteen tools that check a page against the house standards,
and nothing that produces a page meeting them. So every default written into
`web-build-standards` had to be reapplied by hand on every build, and the
expensive ones were the ones quietly skipped.

What makes this more than a starter template is the test beside it: the
generated site is served and the real passes - `seo.js`, `a11y.js`,
`security.js` - are run against it, and must report **no blockers**. If a
standard changes and the scaffold stops meeting it, that test fails.

Tokens come from a `DESIGN.md` when one is given, which closes the loop
`study-reference` opens: measure a real page, write the tokens, build with
them, then measure the result.

It writes plain HTML on purpose. It is the one output every route can start
from - a static host, a WordPress child theme, or a React port - and it is the
only one the gates can run against without a build step.
"""
import io
import os
import re
import sys

# Verified against the WCAG contrast formula before being written in, because
# a palette that fails AA makes every generated page fail the a11y pass.
# Ratios on white: ink 17.96, muted 6.26, white on accent 6.71.
TOKENS = {
    "ink": "#15171a",
    "muted": "#5b6168",
    "paper": "#ffffff",
    "surface": "#f4f5f7",
    "line": "#d9dde2",
    "accent": "#1c4ed8",
    "accent-ink": "#ffffff",
    # One base unit, stated rather than inferred: 8px with a 4px micro-step.
    "unit": "8px",
    "radius": "10px",
    # One shadow tier, not a ladder. Most surfaces carry none.
    "shadow": "0 6px 24px rgba(21, 23, 26, 0.10)",
    "ease": "cubic-bezier(0.16, 1, 0.3, 1)",
}
# Six sizes, not fourteen. A scale a person can hold in their head.
SCALE = {"xs": "0.875rem", "sm": "1rem", "md": "1.125rem",
         "lg": "1.5rem", "xl": "2rem", "display": "2.5rem"}
# Marketing pages breathe more than dense, card-heavy ones.
SECTION_PAD = {"marketing": "88px", "dense": "64px"}

DASHES = re.compile(r"[–—]|&#821[12];|&[mn]dash;")


def read_design(path):
    """Pull tokens out of a DESIGN.md written by study-reference.

    Only values that are obviously colours or lengths are taken. A DESIGN.md is
    measured from somebody's live site, so a malformed line is likely and a
    half-applied palette is worse than none: anything unparsed keeps the
    default rather than becoming an empty custom property.
    """
    out = {}
    if not path or not os.path.isfile(path):
        return out
    body = io.open(path, encoding="utf-8", errors="replace").read()
    for key, pats in (
            ("accent", (r"(?i)^\s*primary\s*:\s*(#[0-9a-f]{3,8})",
                        r"(?i)^\s*accent\s*:\s*(#[0-9a-f]{3,8})")),
            ("ink", (r"(?i)^\s*(?:ink|text|foreground)\s*:\s*(#[0-9a-f]{3,8})",)),
            ("paper", (r"(?i)^\s*(?:paper|background|bg)\s*:\s*(#[0-9a-f]{3,8})",)),
            ("radius", (r"(?i)^\s*radius\s*:\s*(\d+px)",)),
            ("unit", (r"(?i)^\s*(?:base[- ]unit|spacing[- ]base)\s*:\s*(\d+px)",)),
    ):
        for p in pats:
            m = re.search(p, body, re.M)
            if m:
                out[key] = m.group(1)
                break
    return out


def description(name, kind):
    """A meta description inside the 150 to 160 band, without padding words.

    seo.js gates at 160 and aims for 150 to 160, so a scaffold that ships 90
    characters would fail its own standard on day one.
    """
    base = ("%s helps you get the job done properly, with clear pricing, work "
            "you can check and someone who answers the phone. Get in touch to "
            "talk it through." % name)
    if len(base) > 160:
        base = base[:157].rsplit(" ", 1)[0] + "..."
    while len(base) < 150:
        base = base.rstrip(".") + ". Ask us anything."
        if len(base) > 160:
            base = base[:157].rsplit(" ", 1)[0] + "..."
            break
    return base


def css(tokens, kind):
    t = dict(TOKENS)
    t.update(tokens or {})
    pad = SECTION_PAD.get(kind, SECTION_PAD["marketing"])
    rows = "\n".join("  --%s: %s;" % (k, v) for k, v in sorted(t.items()))
    sizes = "\n".join("  --text-%s: %s;" % (k, v) for k, v in SCALE.items())
    return """/* Tokens. Components reference these and never a raw value: the
   hard-coded one is what gets missed when the palette changes, and three
   slightly different reds on one page is the giveaway. */
:root {
%(rows)s
%(sizes)s
  --header-h: 64px;
  --section-pad: %(pad)s;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ink: #f2f3f5;
    --muted: #a8aeb6;
    --paper: #121417;
    --surface: #1b1e22;
    --line: #2b3036;
  }
}
:root[data-theme="dark"] {
  --ink: #f2f3f5; --muted: #a8aeb6; --paper: #121417;
  --surface: #1b1e22; --line: #2b3036;
}

*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%%; }
/* Deliberately absent: scroll-behavior: smooth. It fights Lenis, and this
   page routes anchors through the script instead. */
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 400 var(--text-sm)/1.65 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}

/* Never below 14px on a phone. */
@media (max-width: 480px) { body { font-size: var(--text-xs); } }

img { max-width: 100%%; height: auto; display: block; }
a { color: var(--accent); }

/* The most common accessibility defect there is, is outline:none with nothing
   put back. This is what is put back. */
:focus-visible {
  outline: 3px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}

.skip {
  position: absolute; left: -9999px; top: 0;
  background: var(--paper); color: var(--ink);
  padding: calc(var(--unit) * 1.5); z-index: 100;
}
.skip:focus { left: var(--unit); }

.wrap { width: min(1120px, 100%% - calc(var(--unit) * 4)); margin-inline: auto; }

/* --- the overflow fixes, measured at 320 and 360px on a live site ------- */
.grid > *, .flex-row > * { min-width: 0; }
h1, h2, h3 { overflow-wrap: break-word; }
@media (max-width: 480px) { h1, h2, h3 { hyphens: auto; } }
.row { display: flex; gap: var(--unit); flex-wrap: wrap; }
.row b, .row a { overflow-wrap: anywhere; }
.stats { display: grid; gap: calc(var(--unit) * 2);
         grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (min-width: 768px) { .stats { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.hero-cta .btn { white-space: normal; text-align: center; justify-content: center; }

/* --- header that becomes a centred pill on scroll ----------------------- */
.site-head {
  position: sticky; top: 0; z-index: 50;
  background: color-mix(in srgb, var(--paper) 88%%, transparent);
  border-bottom: 1px solid var(--line);
  transition: max-width 320ms var(--ease), border-radius 320ms var(--ease),
              margin 320ms var(--ease), background 320ms var(--ease),
              box-shadow 320ms var(--ease);
}
.site-head[data-pinned="true"] {
  max-width: 980px; margin: var(--unit) auto 0;
  border-radius: 999px; border-color: transparent;
  box-shadow: var(--shadow);
  backdrop-filter: blur(10px);
}
.site-head .wrap { display: flex; align-items: center; justify-content: space-between;
                   min-height: var(--header-h); gap: var(--unit); }
.brand { font-weight: 650; font-size: var(--text-md); text-decoration: none; color: var(--ink); }
.site-nav { display: flex; gap: calc(var(--unit) * 2); }
.site-nav a { color: var(--ink); text-decoration: none; }
.site-nav a:hover { text-decoration: underline; }

/* --- hero fits the first screen ----------------------------------------- */
.hero {
  display: grid; align-content: center;
  min-height: calc(100vh - var(--header-h));
  min-height: calc(100svh - var(--header-h));
  padding-block: calc(var(--unit) * 5);
}
@media (max-height: 900px) { .hero { padding-block: calc(var(--unit) * 3); } }
/* Modest display weight. The loud moment on this page is the one number
   below, not the heading. */
.hero h1 { font-size: var(--text-xl); line-height: 1.15; margin: 0 0 var(--unit); font-weight: 650; }
@media (min-width: 768px) { .hero h1 { font-size: var(--text-display); } }
.hero p { font-size: var(--text-md); color: var(--muted); max-width: 56ch; margin: 0 0 calc(var(--unit) * 3); }
.hero-cta { display: flex; gap: var(--unit); flex-wrap: wrap; }

/* 44x44 minimum, every time. */
.btn {
  display: inline-flex; align-items: center; min-height: 44px;
  padding: 0 calc(var(--unit) * 2.5);
  border: 1px solid var(--accent); border-radius: var(--radius);
  background: var(--accent); color: var(--accent-ink);
  font: inherit; font-weight: 600; text-decoration: none; cursor: pointer;
  transition: transform 180ms var(--ease), box-shadow 180ms var(--ease);
}
.btn--quiet { background: transparent; color: var(--accent); }

section { padding-block: var(--section-pad); }
section h2 { font-size: var(--text-lg); margin: 0 0 calc(var(--unit) * 2); font-weight: 650; }

.cards { display: grid; gap: calc(var(--unit) * 2); grid-template-columns: repeat(auto-fit, minmax(min(260px, 100%%), 1fr)); }
/* Flat by default. Depth from surface colour and spacing, not a shadow on
   every card. */
.card { background: var(--surface); border: 1px solid var(--line);
        border-radius: var(--radius); padding: calc(var(--unit) * 3); }
.card h3 { margin: 0 0 var(--unit); font-size: var(--text-md); font-weight: 650; }
.card p { margin: 0; color: var(--muted); }

/* The one loud thing on the page. */
.figure { font-size: 3.5rem; line-height: 1; font-weight: 700; letter-spacing: -0.02em; }
.figure + span { color: var(--muted); }

.media { overflow: hidden; border-radius: var(--radius); }
.media img { transition: transform 420ms var(--ease); }

form { display: grid; gap: calc(var(--unit) * 2); max-width: 520px; }
label { display: block; font-weight: 600; margin-bottom: calc(var(--unit) * 0.5); }
input, textarea {
  width: 100%%; min-height: 44px; padding: calc(var(--unit) * 1.25);
  font: inherit; color: var(--ink); background: var(--paper);
  border: 1px solid var(--line); border-radius: var(--radius);
}
textarea { min-height: 120px; }
.hint { color: var(--muted); font-size: var(--text-xs); }
.error { color: #a4161a; font-weight: 600; }
:root[data-theme="dark"] .error,
@media (prefers-color-scheme: dark) { .error { color: #ff8a8a; } }
[hidden] { display: none !important; }
.ok { background: var(--surface); border: 1px solid var(--line);
      border-radius: var(--radius); padding: calc(var(--unit) * 3); }

.site-foot { border-top: 1px solid var(--line); padding-block: calc(var(--unit) * 4);
             color: var(--muted); }

/* --- motion, only when it is wanted ------------------------------------- */
@media (prefers-reduced-motion: no-preference) {
  .reveal { opacity: 0; transform: translateY(20px);
            transition: opacity 600ms var(--ease), transform 600ms var(--ease); }
  .reveal.is-in { opacity: 1; transform: none; }
  .btn:hover { transform: translateY(-3px); box-shadow: var(--shadow); }
  .card:hover { transform: translateY(-4px); }
  .card { transition: transform 200ms var(--ease); }
  .media:hover img { transform: scale(1.05); }
}
@media (prefers-reduced-motion: reduce) {
  .reveal { opacity: 1; transform: none; }
}
""" % {"rows": rows, "sizes": sizes, "pad": pad}


JS = """/* No framework, because a static page should not need one. Reveals use an
   IntersectionObserver with CSS transitions, which is what web-build-standards
   prescribes for plain HTML and WordPress.

   Lenis is not loaded here. On a React or Next build, add it at the layout
   root, remove any scroll-behavior:smooth, and route anchors through
   lenis.scrollTo - the anchor handler below is the stand-in for that. */
(function () {
  "use strict";
  var calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Section reveal: fade plus a 20px rise, staggered 80ms between siblings.
  if (!calm && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e, i) {
        if (!e.isIntersecting) return;
        var el = e.target;
        setTimeout(function () { el.classList.add("is-in"); }, i * 80);
        io.unobserve(el);
      });
    }, { rootMargin: "0px 0px -10% 0px", threshold: 0.1 });
    document.querySelectorAll(".reveal").forEach(function (el) { io.observe(el); });
  } else {
    document.querySelectorAll(".reveal").forEach(function (el) {
      el.classList.add("is-in");
    });
  }

  // The header pulls into a centred pill once the page has moved.
  var head = document.querySelector(".site-head");
  if (head) {
    var onScroll = function () {
      head.setAttribute("data-pinned", String(window.scrollY > 24));
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  // Anchors, so a hash never jumps past a smooth-scroll library.
  document.addEventListener("click", function (ev) {
    var a = ev.target.closest('a[href^="#"]');
    if (!a) return;
    var id = a.getAttribute("href").slice(1);
    var target = id && document.getElementById(id);
    if (!target) return;
    ev.preventDefault();
    target.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
    target.setAttribute("tabindex", "-1");
    target.focus({ preventScroll: true });
  });

  // The form. Validation messages sit next to the field that failed, and the
  // success state replaces the fields rather than being a toast.
  var form = document.getElementById("enquiry");
  if (!form) return;
  form.addEventListener("submit", function (ev) {
    var bad = null;
    form.querySelectorAll("[required]").forEach(function (f) {
      var msg = document.getElementById(f.id + "-error");
      var ok = f.checkValidity();
      if (msg) {
        msg.hidden = ok;
        msg.textContent = ok ? "" : (f.dataset.error || "This field is required.");
      }
      f.setAttribute("aria-invalid", String(!ok));
      if (!ok && !bad) bad = f;
    });
    if (bad) {
      ev.preventDefault();
      bad.focus();
      return;
    }
    // Leave the real submission to the back end this gets wired to. The
    // success panel below is shown by the server's response or by the handler
    // replacing it - never by the front end pretending the send worked, which
    // is the failure this whole skill is about.
  });
})();
"""


def page(name, domain, title, desc, h1, body, slug, kind, nav):
    url = "https://%s/%s" % (domain, slug if slug != "index" else "")
    org_id = "https://%s/#organization" % domain
    crumbs = ""
    if slug != "index":
        crumbs = """,
    {"@type": "BreadcrumbList", "itemListElement": [
      {"@type": "ListItem", "position": 1, "name": "Home",
       "item": "https://%s/"},
      {"@type": "ListItem", "position": 2, "name": %s, "item": "%s"}
    ]}""" % (domain, '"' + title.split(" - ")[0] + '"', url)
    # No telephone and no address in the schema. Both or neither: a phone with
    # no postal address is incomplete and seo.js reports it, and a placeholder
    # address would be worse - a placeholder inside structured data is read by
    # a validator as the real value. The README says to add the pair together
    # once the client has confirmed them.
    ld = """{"@context": "https://schema.org", "@graph": [
    {"@type": "Organization", "@id": "%(org)s", "name": "%(name)s",
     "url": "https://%(domain)s/",
     "logo": {"@type": "ImageObject", "url": "https://%(domain)s/assets/logo.svg"}},
    {"@type": "WebSite", "@id": "https://%(domain)s/#website",
     "url": "https://%(domain)s/", "name": "%(name)s",
     "publisher": {"@id": "%(org)s"}, "inLanguage": "en"}%(crumbs)s
  ]}""" % {"org": org_id, "name": name, "domain": domain, "crumbs": crumbs}

    links = "".join(
        '<a href="%s"%s>%s</a>' % (href, ' aria-current="page"' if href == (
            "/" if slug == "index" else "/" + slug + ".html") else "", label)
        for label, href in nav)

    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(url)s">
<meta property="og:type" content="website">
<meta property="og:url" content="%(url)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:image" content="https://%(domain)s/assets/share.jpg">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="%(title)s">
<meta name="twitter:description" content="%(desc)s">
<meta name="twitter:image" content="https://%(domain)s/assets/share.jpg">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="stylesheet" href="/assets/site.css">
<script type="application/ld+json">%(ld)s</script>
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header class="site-head">
  <div class="wrap">
    <a class="brand" href="/">%(name)s</a>
    <nav class="site-nav" aria-label="Primary">%(links)s</nav>
  </div>
</header>
<main id="main">
%(body)s
</main>
<footer class="site-foot">
  <div class="wrap">
    <p class="row"><span>%(name)s</span> <a href="tel:+441134960000">0113 496 0000</a>
    <a href="/contact.html">Contact</a></p>
  </div>
</footer>
<script src="/assets/site.js"></script>
</body>
</html>
""" % {"title": title, "desc": desc, "url": url, "domain": domain, "ld": ld,
       "name": name, "links": links, "body": body}


def home_body(name):
    return """<section class="hero">
  <div class="wrap">
    <h1>Work you can check, from people who answer the phone</h1>
    <p>%(name)s takes on the jobs other firms leave half finished. Clear pricing
    agreed before anything starts, and a written record of what was done.</p>
    <div class="hero-cta">
      <a class="btn" href="/contact.html">Ask for a quote</a>
      <a class="btn btn--quiet" href="#what-we-do">See what we do</a>
    </div>
  </div>
</section>

<section id="what-we-do" class="reveal">
  <div class="wrap">
    <h2>What we do</h2>
    <div class="cards">
      <article class="card"><h3>Assessment</h3><p>We look at the whole job and
      tell you what it needs, in writing, before any work is agreed.</p></article>
      <article class="card"><h3>The work itself</h3><p>Carried out to the
      specification agreed, by the person who quoted it, on the dates given.</p></article>
      <article class="card"><h3>Afterwards</h3><p>A record of what changed, what
      was replaced, and what to watch for over the next year.</p></article>
    </div>
  </div>
</section>

<section class="reveal">
  <div class="wrap">
    <h2>By the numbers</h2>
    <div class="stats">
      <div><span class="figure">PLACEHOLDER</span> <span>jobs completed</span></div>
      <div><p class="hint">Replace every figure on this page with one the client
      has confirmed. An invented number is the fastest way to lose a project.</p></div>
    </div>
  </div>
</section>
""" % {"name": name}


CONTACT_BODY = """<section>
  <div class="wrap">
    <h1>Contact us</h1>
    <p>Tell us what the job is and we will come back with a price and a date.</p>
    <form id="enquiry" method="post" action="/enquiry">
      <div>
        <label for="name">Your name</label>
        <input id="name" name="name" type="text" autocomplete="name" required
               data-error="Please tell us your name so we can reply to you.">
        <p class="error" id="name-error" hidden></p>
      </div>
      <div>
        <label for="email">Email address</label>
        <input id="email" name="email" type="email" autocomplete="email" required
               data-error="Please enter an email address we can reply to.">
        <p class="error" id="email-error" hidden></p>
      </div>
      <div>
        <label for="phone">Phone number</label>
        <input id="phone" name="phone" type="tel" autocomplete="tel"
               inputmode="tel">
        <p class="hint" id="phone-hint">Optional. Useful if the job needs a visit.</p>
      </div>
      <div>
        <label for="job">What do you need doing?</label>
        <textarea id="job" name="job" required
                  data-error="A sentence about the job is enough to start."></textarea>
        <p class="error" id="job-error" hidden></p>
      </div>
      <button class="btn" type="submit">Send enquiry</button>
    </form>
    <div class="ok" id="sent" hidden>
      <h2>Thank you, your enquiry has been sent</h2>
      <p>We reply to everything within one working day.</p>
    </div>
  </div>
</section>
"""

NOTFOUND_BODY = """<section>
  <div class="wrap">
    <h1>That page is not here</h1>
    <p>The address may have changed. Try the <a href="/">home page</a> or
    <a href="/contact.html">contact us</a> and we will point you at it.</p>
  </div>
</section>
"""


def write(out, rel, body):
    p = os.path.join(out, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(body)
    return rel


def build(out, name, domain, design=None, kind="marketing"):
    tokens = read_design(design)
    desc_home = description(name, kind)
    desc_contact = ("Tell %s what you need doing and get a price and a date "
                    "back. Phone, email or the enquiry form, answered within "
                    "one working day." % name)
    while len(desc_contact) < 150:
        desc_contact += " No obligation."
    desc_contact = desc_contact[:160]

    nav = [("Home", "/"), ("Contact", "/contact.html")]
    written = []
    # The title opens with the same words as the h1. Matching them is what
    # keeps Google from rewriting the title, and the house format is
    # "main content - brand" with one separator.
    written.append(write(out, "index.html", page(
        name, domain, "Work you can check - %s" % name, desc_home,
        None, home_body(name), "index", kind, nav)))
    written.append(write(out, "contact.html", page(
        name, domain, "Contact us - %s" % name, desc_contact,
        None, CONTACT_BODY, "contact", kind, nav)))
    written.append(write(out, "404.html", page(
        name, domain, "Page not found - %s" % name,
        desc_contact, None, NOTFOUND_BODY, "404", kind, nav)))
    written.append(write(out, "assets/site.css", css(tokens, kind)))
    written.append(write(out, "assets/site.js", JS))

    written.append(write(out, "robots.txt",
                         "User-agent: *\nAllow: /\n\n"
                         "Sitemap: https://%s/sitemap.xml\n" % domain))
    written.append(write(out, "sitemap.xml",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        '  <url><loc>https://%s/</loc></url>\n'
        '  <url><loc>https://%s/contact.html</loc></url>\n'
        '</urlset>\n' % (domain, domain)))
    written.append(write(out, "llms.txt",
        "# %s\n\n> %s\n\n## Pages\n"
        "- [Home](https://%s/): what the business does and who it is for\n"
        "- [Contact](https://%s/contact.html): how to get a price and a date\n\n"
        "Every figure on this site marked PLACEHOLDER still needs the client's\n"
        "confirmed number. Nothing here may be quoted until it is replaced.\n"
        % (name, desc_home, domain, domain)))

    # Security headers, in the two forms most hosts take. security.js checks
    # these on a real domain; on localhost it skips them, so they are shipped
    # rather than assumed.
    headers = ("/*\n"
               "  Strict-Transport-Security: max-age=63072000; includeSubDomains\n"
               "  Content-Security-Policy: default-src 'self'; img-src 'self' data:; "
               "style-src 'self'; script-src 'self'; frame-ancestors 'none'; "
               "base-uri 'self'; form-action 'self'\n"
               "  X-Content-Type-Options: nosniff\n"
               "  Referrer-Policy: strict-origin-when-cross-origin\n"
               "  Permissions-Policy: geolocation=(), microphone=(), camera=()\n")
    written.append(write(out, "_headers", headers))
    written.append(write(out, "vercel.json",
        '{\n  "headers": [\n    {\n      "source": "/(.*)",\n'
        '      "headers": [\n'
        '        {"key": "Strict-Transport-Security", "value": "max-age=63072000; includeSubDomains"},\n'
        '        {"key": "X-Content-Type-Options", "value": "nosniff"},\n'
        '        {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},\n'
        '        {"key": "Content-Security-Policy", "value": "default-src \'self\'; '
        'img-src \'self\' data:; style-src \'self\'; script-src \'self\'; '
        'frame-ancestors \'none\'; base-uri \'self\'; form-action \'self\'"}\n'
        '      ]\n    }\n  ]\n}\n'))

    written.append(write(out, "README.md",
        "# %(name)s\n\n"
        "Generated by `web-build-standards/scaffold.py`. It already meets the\n"
        "house standards and passes `seo.js`, `a11y.js` and `security.js` with\n"
        "no blockers. What it does **not** have is content.\n\n"
        "## Before this goes anywhere near a client\n\n"
        "1. Replace every `PLACEHOLDER` with a figure the client has confirmed.\n"
        "   An invented number is the fastest way to lose a project.\n"
        "2. Replace the phone number. The one shipped is 0113 496 0000, which\n"
        "   is inside Ofcom's range reserved for documentation, so it can never\n"
        "   reach a real person. Put the real one in the markup **and** add\n"
        "   `telephone` and `address` together to the Organization block in the\n"
        "   JSON-LD - both or neither, because a phone with no postal address\n"
        "   is reported, and a placeholder address is read by a validator as\n"
        "   the real thing. `seo.js` checks that the schema and the page agree.\n"
        "3. Point the form's `action` at a real handler and **submit a real\n"
        "   test**, then confirm it arrived at the destination. A success\n"
        "   panel is not confirmation - see `forms-and-leads`.\n"
        "4. Add the real favicon and a 1200x630 share image at the paths the\n"
        "   head already references.\n"
        "5. Run `fix-job` as a `golive` job before launching.\n\n"
        "## What is deliberately not here\n\n"
        "- **Lenis.** This is plain HTML, so reveals use an IntersectionObserver.\n"
        "  On a React or Next port, add Lenis at the layout root, delete any\n"
        "  `scroll-behavior: smooth`, and route anchors through `lenis.scrollTo`.\n"
        "- **Images.** Add them with `width`, `height`, `srcset` and real `alt`,\n"
        "  and `loading=\"lazy\"` only below the fold.\n"
        "- **A cookie banner.** Add one only if something actually sets a\n"
        "  non-essential cookie.\n" % {"name": name}))
    return written


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    flag = lambda f, d=None: (sys.argv[sys.argv.index(f) + 1]
                              if f in sys.argv and
                              sys.argv.index(f) + 1 < len(sys.argv) else d)
    out = os.path.abspath(args[0])
    name = flag("--name", "The Business")
    domain = (flag("--domain", "example.com") or "").replace("https://", "")\
        .replace("http://", "").strip("/")
    kind = flag("--kind", "marketing")
    if os.path.isdir(out) and os.listdir(out):
        print("refusing to write into a folder that is not empty: %s" % out)
        print("A scaffold overwriting somebody's work is not recoverable.")
        return 2
    files = build(out, name, domain, flag("--design"), kind)
    print("wrote %d file(s) into %s" % (len(files), out))
    for f in files:
        print("  " + f)
    print("\nRead README.md first. It lists what has to be replaced before this\n"
          "goes near a client, starting with every PLACEHOLDER figure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
