/**
 * Does the SEO pass produce the numbers seo-complete demands, and refuse to
 * state the ones it cannot honestly know?
 *
 * The case that matters most is the soft 404. On a site that answers 200 for
 * every unknown path, a broken internal link answers 200 too - so a status-code
 * link check reports a clean site that is full of dead links. The tool has to
 * notice that first and say the link count means nothing until it is fixed.
 *
 *   node seotest.js
 */
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const S = require("./seo.js");

const RESULTS = [];
function ok(name, cond, extra) {
  RESULTS.push(!!cond);
  console.log(`${cond ? "PASS " : "FAIL "} ${name}${extra ? "  [" + String(extra).slice(0, 120) + "]" : ""}`);
}
const ids = (l) => (l || []).map((f) => f.id);
const has = (l, id) => ids(l).includes(id);
const sevOf = (l, id) => (l || []).find((f) => f.id === id)?.sev;

// ------------------------------------------------------------ pure checks

ok("a title inside the limit is clean",
   !has(S.judgeTitle("Dance Photography in Houston - Studio", "Dance Photography in Houston"), "title-long"));
ok("a title over 60 is reported with its length",
   /\b72 characters\b/.test((S.judgeTitle("x".repeat(72)) || [])[0].title));
ok("a missing title says Missing, not Not Found",
   S.judgeTitle("")[0].title === "Title is Missing");
ok("a double-encoded ampersand in a title is caught",
   has(S.judgeTitle("Bath &amp; Body"), "title-entity"),
   "it renders as five literal characters");
ok("a correctly decoded ampersand is not a finding",
   !has(S.judgeTitle("Bath & Body"), "title-entity"));
ok("a title chopped by four separators is reported",
   has(S.judgeTitle("A | B | C | D"), "title-separators"));
ok("one separator is fine",
   !has(S.judgeTitle("Main subject - Brand"), "title-separators"));
ok("a superlative is reported, because Google rewrites it",
   has(S.judgeTitle("Best Plumber in Leeds"), "title-superlative"));
ok("a title aligned with the H1 raises no drift note",
   !has(S.judgeTitle("Dance Photography Houston", "Dance Photography Houston studio"),
        "title-h1-drift"));
ok("a title that opens differently from the H1 is noted",
   has(S.judgeTitle("Contact Us Today", "Dance Photography Houston"), "title-h1-drift"));

ok("a description over 160 is reported",
   has(S.judgeDescription("x".repeat(170)), "desc-long"));
ok("160 exactly is accepted", !has(S.judgeDescription("x".repeat(160)), "desc-long"),
   "the gate is 160, the band is 150-160");
ok("a short description is a note, not a defect",
   sevOf(S.judgeDescription("x".repeat(80)), "desc-short") === "NOTE");
ok("155 no longer counts as too long",
   !has(S.judgeDescription("x".repeat(155)), "desc-long"),
   "the limit moved from 155 to 160 on purpose");
ok("a missing description says Missing",
   S.judgeDescription("")[0].title === "Meta description is Missing");

ok("no H1 is reported", has(S.judgeH1([]), "h1-missing"));
ok("two H1s are reported", has(S.judgeH1(["a", "b"]), "h1-multiple"));
ok("one H1 inside 60 is clean", S.judgeH1(["A clear heading"]).length === 0);
ok("an H1 over 60 is reported", has(S.judgeH1(["x".repeat(61)]), "h1-long"));

// ------------------------------------------------------- address variants

const allLive = [
  { url: "https://a.example/", scheme: "https", status: 200, final: "https://a.example/" },
  { url: "http://a.example/", scheme: "http", status: 200, final: "http://a.example/" },
  { url: "https://www.a.example/", scheme: "https", status: 200, final: "https://www.a.example/" },
  { url: "http://www.a.example/", scheme: "http", status: 200, final: "http://www.a.example/" },
];
ok("four addresses all serving 200 is a blocker",
   sevOf(S.judgeVariants(allLive), "duplicate-variants") === "BLOCKER",
   "duplicate content, and each one looks fine alone");
ok("http serving without redirecting is called out separately",
   has(S.judgeVariants(allLive), "http-no-redirect"));

const proper = [
  { url: "https://a.example/", scheme: "https", status: 200, final: "https://a.example/" },
  { url: "http://a.example/", scheme: "http", status: 200, final: "https://a.example/" },
  { url: "https://www.a.example/", scheme: "https", status: 200, final: "https://a.example/" },
  { url: "http://www.a.example/", scheme: "http", status: 200, final: "https://a.example/" },
];
ok("four variants converging on one address is clean",
   S.judgeVariants(proper).length === 0, ids(S.judgeVariants(proper)));
ok("nothing answering at all is a blocker",
   has(S.judgeVariants([{ url: "https://a.example/", scheme: "https", status: 0 }]),
       "no-variant-200"));

ok("a missing canonical is reported",
   has(S.judgeCanonical([{ url: "/", ok: true }]), "canonical-missing"));
ok("variants disagreeing about the canonical is reported",
   has(S.judgeCanonical([
     { url: "https://a.example/", ok: true, canonical: "https://a.example/", isVariant: true },
     { url: "https://www.a.example/", ok: true, canonical: "https://www.a.example/", isVariant: true }]),
     "canonical-inconsistent"));
ok("og:url that disagrees with the canonical is reported",
   has(S.judgeCanonical([{ url: "/", ok: true, canonical: "https://a.example/",
                           ogUrl: "https://www.a.example/" }]), "og-url-mismatch"));

// ------------------------------------------------------------- robots.txt

ok("robots.txt blocking an AI crawler is reported",
   has(S.judgeRobots("User-agent: GPTBot\nDisallow: /\n", 200), "ai-blocked"));
ok("and it names which one",
   /GPTBot/.test((S.judgeRobots("User-agent: GPTBot\nDisallow: /", 200)
     .find((f) => f.id === "ai-blocked") || {}).title));
ok("it explains that search reporting will not show it",
   /search reporting/.test((S.judgeRobots("User-agent: ClaudeBot\nDisallow: /", 200)
     .find((f) => f.id === "ai-blocked") || {}).detail || ""));
ok("a normal robots.txt with a sitemap is clean",
   S.judgeRobots("User-agent: *\nAllow: /\nSitemap: https://a.example/sitemap.xml", 200)
     .length === 0);
ok("disallowing everything for everyone is reported",
   has(S.judgeRobots("User-agent: *\nDisallow: /", 200), "all-blocked"));
ok("a missing sitemap directive is a minor",
   sevOf(S.judgeRobots("User-agent: *\nAllow: /", 200), "robots-no-sitemap") === "MINOR");
ok("a missing robots.txt says Missing and is not fatal",
   sevOf(S.judgeRobots("", 404), "robots-missing") === "MINOR");
ok("blocking only a scraper that is not an AI answer engine is not flagged",
   !has(S.judgeRobots("User-agent: SemrushBot\nDisallow: /\nSitemap: https://a/s.xml", 200),
        "ai-blocked"));

// ------------------------------------------------------- the soft 404

let v = S.judge404(404, "Not found", "<html>home</html>");
ok("a real 404 is no finding and link checking stays trusted",
   v.findings.length === 0 && v.softs === false);
v = S.judge404(200, "<html><div id=root></div></html>", "<html><div id=root></div></html>");
ok("a 200 for an impossible path is reported", has(v.findings, "soft-404"));
ok("and it flips link checking to untrusted", v.softs === true,
   "a broken link answers 200 on this site too");
ok("it says the same shell is being served when it is",
   /same shell/.test(v.findings[0].detail));
ok("a 500 for an invalid path is reported but is not a soft 404",
   has(S.judge404(500, "", "").findings, "404-server-error")
   && S.judge404(500, "", "").softs === false);

ok("link checking is refused outright on a soft-404 site",
   has(S.judgeLinks([{ url: "/a", verdict: "ok" }], true), "links-unverifiable"));
ok("and the refusal says the count means nothing",
   /means nothing/.test((S.judgeLinks([], true)[0] || {}).detail || ""));

// --------------------------------------------------------------- links

ok("200 is ok when the site 404s properly", S.classifyLink(200, false) === "ok");
ok("200 is unverifiable when the site soft-404s", S.classifyLink(200, true) === "unverifiable");
ok("404 is broken", S.classifyLink(404, false) === "broken");
ok("403 is blocked, not broken", S.classifyLink(403, false) === "blocked",
   "a refusal is about who is asking");
ok("429 is blocked, not broken", S.classifyLink(429, false) === "blocked");
ok("301 is a redirect", S.classifyLink(301, false) === "redirect");
ok("500 is an error", S.classifyLink(500, false) === "error");

const mixed = [
  { url: "/gone", foundOn: "/", verdict: "broken" },
  { url: "/old", foundOn: "/", verdict: "redirect" },
  { url: "/locked", foundOn: "/", verdict: "blocked" },
];
ok("a broken internal link is a blocker",
   sevOf(S.judgeLinks(mixed, false), "links-broken") === "BLOCKER");
ok("the broken finding names the page it was found on",
   /on \//.test((S.judgeLinks(mixed, false).find((f) => f.id === "links-broken") || {}).detail));
ok("a redirecting link is a minor, not an error",
   sevOf(S.judgeLinks(mixed, false), "links-redirect") === "MINOR");
ok("a blocked link is a note and is kept out of the broken count",
   sevOf(S.judgeLinks(mixed, false), "links-blocked") === "NOTE");

// -------------------------------------------------------------- sitemap

ok("a missing sitemap says Missing",
   S.judgeSitemap({ ok: false })[0].title === "sitemap.xml is Missing");
ok("duplicate sitemap URLs are reported",
   has(S.judgeSitemap({ ok: true, count: 9, duplicates: 2 }), "sitemap-duplicates"));
ok("sitemap URLs that redirect are reported",
   has(S.judgeSitemap({ ok: true, count: 9, redirecting: ["/a"] }), "sitemap-redirects"));
ok("and it says listing them is the error, not the redirect",
   /listing them is the/.test((S.judgeSitemap({ ok: true, count: 1, redirecting: ["/a"] })
     .find((f) => f.id === "sitemap-redirects") || {}).detail));
ok("a clean sitemap is no finding",
   S.judgeSitemap({ ok: true, count: 12, duplicates: 0, redirecting: [] }).length === 0);

// ----------------------------------------------------------------- page

const noLd = S.judgePage({ url: "/", ok: true, title: "A fine title",
                           description: "x".repeat(155), h1: ["A fine heading"],
                           canonical: "/", rawJsonLd: false, domJsonLd: true,
                           og: true, twitter: true });
ok("JSON-LD only in the DOM is reported as not server-rendered",
   has(noLd, "jsonld-not-server-rendered"));
ok("and it explains a crawler never sees it",
   /after hydration/.test((noLd.find((f) => f.id === "jsonld-not-server-rendered") || {}).detail));
ok("a noindexed page is a blocker",
   sevOf(S.judgePage({ url: "/", ok: true, title: "t", description: "x".repeat(155),
                       h1: ["h"], rawJsonLd: true, og: true, twitter: true,
                       noindex: true, noindexFrom: "the robots meta tag" }),
         "noindex") === "BLOCKER");
ok("every page finding carries the page it is about",
   noLd.every((f) => f.where === "/"));

ok("findings come out worst first",
   S.sortFindings([{ sev: "NOTE", title: "n" }, { sev: "BLOCKER", title: "b" }])
     .map((f) => f.sev).join(",") === "BLOCKER,NOTE");

const txt = S.report({ url: "https://a.example", pagesRead: 3, linksChecked: 10,
                       findings: [], counts: { "pages read": 3 }, linkCap: 50,
                       linkCapHit: true });
ok("the report says when the link cap was reached", /not the whole site/.test(txt));
ok("the report states the blocked-not-broken rule", /never as broken/.test(txt));
ok("the report states the Missing rule", /never as Not Found/.test(txt));
const softTxt = S.report({ url: "https://a.example", findings: [], softs: true,
                           counts: {} });
ok("a soft-404 site is warned about at the top of the report",
   /unreliable until that is fixed/.test(softTxt));

// -------------------------------------------------------- against a page

const GOOD = (slug) => `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>${slug} page - Demo</title>
<meta name="description" content="${"A clear description of the ".repeat(4)}page here ok.">
<link rel="canonical" href="http://127.0.0.1:PORT/${slug}">
<meta property="og:url" content="http://127.0.0.1:PORT/${slug}">
<meta property="og:title" content="${slug}">
<meta name="twitter:card" content="summary">
<script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","name":"Demo"}</script>
</head><body><h1>${slug} page</h1>
<nav><a href="/about">About</a><a href="/gone">Dead</a></nav>
<img src="/a.png" alt="a thing"><img src="/b.png">
<p>Body copy.</p></body></html>`;

function serve(soft) {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const url = req.url.split("?")[0];
      const send = (code, type, body) => {
        res.writeHead(code, { "content-type": type });
        res.end(body);
      };
      const port = srv.address().port;
      const page = (slug) => GOOD(slug).replace(/PORT/g, String(port));
      if (url === "/robots.txt") {
        return send(200, "text/plain",
                    "User-agent: *\nAllow: /\nUser-agent: GPTBot\nDisallow: /\n"
                    + "Sitemap: http://127.0.0.1:" + port + "/sitemap.xml\n");
      }
      if (url === "/sitemap.xml") {
        return send(200, "application/xml",
          '<?xml version="1.0"?><urlset>'
          + ["/", "/about"].map((u) => "<loc>http://127.0.0.1:" + port + u + "</loc>").join("")
          + "</urlset>");
      }
      if (url === "/" ) return send(200, "text/html; charset=utf-8", page("Home"));
      if (url === "/about") return send(200, "text/html; charset=utf-8", page("About"));
      if (url === "/gone") {
        return soft ? send(200, "text/html; charset=utf-8", page("Home"))
                    : send(404, "text/html", "<h1>Not found</h1>");
      }
      // every other path
      return soft ? send(200, "text/html; charset=utf-8", page("Home"))
                  : send(404, "text/html", "<h1>Not found</h1>");
    });
    srv.listen(0, "127.0.0.1", () => resolve({ srv, port: srv.address().port }));
  });
}

function runCli(url, out, extra) {
  return new Promise((resolve) => {
    // spawn, not execFileSync: the fixture server runs in this process and a
    // blocking call stops it answering, which looks exactly like a browser fault.
    const p = spawn(process.execPath,
      [path.join(__dirname, "seo.js"), url, "--out", out, "--pages", "3",
       "--max-links", "10", ...(extra || [])],
      { stdio: ["ignore", "pipe", "pipe"] });
    let so = "", se = "";
    p.stdout.on("data", (d) => { so += d; });
    p.stderr.on("data", (d) => { se += d; });
    p.on("close", (code) => resolve({ code, so, se }));
  });
}

(async () => {
  // --- a site that 404s properly: the broken link must be found ---------
  let f = await serve(false);
  let out = fs.mkdtempSync(path.join(os.tmpdir(), "seotest-"));
  try {
    const r = await runCli("http://127.0.0.1:" + f.port + "/", out);
    const jf = path.join(out, "seo.json");
    ok("the pass writes a json report", fs.existsSync(jf), r.se.slice(0, 200));
    const d = fs.existsSync(jf) ? JSON.parse(fs.readFileSync(jf, "utf8")) : { findings: [] };
    ok("it reads the pages from the sitemap", d.pagesRead === 2, d.pagesRead);
    ok("the site is not treated as soft-404ing", d.softs === false);
    ok("the dead internal link is found",
       has(d.findings, "links-broken"),
       (d.links || []).map((l) => l.url + "=" + l.status).join(" "));
    ok("the AI crawler block in robots.txt is found", has(d.findings, "ai-blocked"));
    ok("an image with no alt is counted",
       (d.counts || {})["pages read"] === 2 &&
       has(d.findings, "img-alt"));
    ok("server-rendered JSON-LD is accepted",
       !has(d.findings, "jsonld-not-server-rendered"));
    ok("duplicate descriptions across pages are reported",
       has(d.findings, "dupe-description"),
       "both fixture pages share one description");
    ok("a blocker makes it exit non-zero", r.code === 1, "exit " + r.code);
  } finally { f.srv.close(); }

  // --- the same site, soft-404ing: the link count must be refused ------
  f = await serve(true);
  out = fs.mkdtempSync(path.join(os.tmpdir(), "seotest2-"));
  try {
    const r = await runCli("http://127.0.0.1:" + f.port + "/", out);
    const d = JSON.parse(fs.readFileSync(path.join(out, "seo.json"), "utf8"));
    ok("a site answering 200 for everything is detected", d.softs === true);
    ok("the soft 404 itself is reported", has(d.findings, "soft-404"));
    ok("the link check is refused rather than reported clean",
       has(d.findings, "links-unverifiable") && !has(d.findings, "links-broken"),
       "the dead link answers 200 here, so a status check would call it fine");
    ok("the report warns about it before anything else",
       /unreliable until that is fixed/.test(
         fs.readFileSync(path.join(out, "seo.md"), "utf8")));
  } finally { f.srv.close(); }

  const pass = RESULTS.filter(Boolean).length;
  console.log(`\n${pass}/${RESULTS.length} checks passed`);
  process.exit(pass === RESULTS.length ? 0 : 1);
})();
