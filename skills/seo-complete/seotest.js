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

// ------------------------------------------------------------- schema

const LD = (obj) => '<script type="application/ld+json">' + JSON.stringify(obj) + "</script>";

ok("a JSON-LD block is parsed out of raw HTML",
   S.parseLd("<head>" + LD({ "@type": "Organization", name: "X" }) + "</head>")[0].ok);
ok("invalid JSON in a block is caught",
   S.parseLd('<script type="application/ld+json">{nope}</script>')[0].ok === false);
ok("invalid JSON is reported as a finding",
   has(S.judgeSchema(S.parseLd('<script type="application/ld+json">{nope}</script>'), "", "static"),
       "ld-invalid"));
ok("an @graph is flattened into its nodes",
   S.ldNodes(S.parseLd(LD({ "@context": "x", "@graph": [
     { "@type": "Organization" }, { "@type": "WebSite" }] }))).length === 2);
ok("an array block is flattened too",
   S.ldNodes(S.parseLd(LD([{ "@type": "Organization" }, { "@type": "WebSite" }]))).length === 2);

ok("two Organization blocks on one page is a defect",
   has(S.judgeSchema(S.parseLd(LD({ "@type": "Organization", name: "A" })
     + LD({ "@type": "Organization", name: "B" })), "", "static"), "ld-duplicate"),
   "one source of truth");
ok("one Organization block is fine",
   !has(S.judgeSchema(S.parseLd(LD({ "@type": "Organization", name: "A" })), "", "static"),
        "ld-duplicate"));

const dangling = S.judgeSchema(S.parseLd(LD({
  "@type": "WebSite", "@id": "https://x.test/#website",
  publisher: { "@id": "https://x.test/#organization" } })), "", "static");
ok("an @id reference with nothing declaring it is reported",
   has(dangling, "ld-dangling-id"),
   "it reads as complete and resolves to no publisher");
ok("and it says the block reads as complete either way",
   /reads as complete/.test(dangling.find((f) => f.id === "ld-dangling-id").detail));
ok("an @id that is declared on the same page is not reported",
   !has(S.judgeSchema(S.parseLd(LD({ "@graph": [
     { "@type": "Organization", "@id": "https://x.test/#organization" },
     { "@type": "WebSite", publisher: { "@id": "https://x.test/#organization" } }] })),
     "", "static"), "ld-dangling-id"));

ok("an unfilled placeholder in live schema is a major finding",
   sevOf(S.judgeSchema(S.parseLd(LD({ "@type": "Organization", name: "[Business Name]" })),
                       "", "static"), "ld-placeholder") === "MAJOR");
ok("example.com in schema is caught too",
   has(S.judgeSchema(S.parseLd(LD({ "@type": "Organization", url: "https://example.com" })),
                     "", "static"), "ld-placeholder"));
ok("a real value is not flagged as a placeholder",
   !has(S.judgeSchema(S.parseLd(LD({ "@type": "Organization", name: "Bright Dental",
                                     url: "https://brightdental.test" })), "", "static"),
        "ld-placeholder"));

ok("serviceType on LocalBusiness is reported",
   has(S.judgeSchema(S.parseLd(LD({ "@type": "LocalBusiness", serviceType: "Plumbing" })),
                     "", "static"), "ld-servicetype"));
ok("serviceType on Service is correct and not reported",
   !has(S.judgeSchema(S.parseLd(LD({ "@type": "Service", serviceType: "Plumbing" })),
                      "", "static"), "ld-servicetype"));

const faqBad = S.judgeSchema(S.parseLd(LD({ "@type": "FAQPage", mainEntity: [
  { "@type": "Question", name: "Do you offer emergency callouts at night?",
    acceptedAnswer: { "@type": "Answer", text: "Yes." } }] })),
  "We fix taps and boilers across Leeds.", "static");
ok("an FAQ question that is not in the visible text is a major finding",
   sevOf(faqBad, "ld-faq-invisible") === "MAJOR",
   "the markup has to match what a visitor reads");
ok("an FAQ question that is on the page is accepted",
   !has(S.judgeSchema(S.parseLd(LD({ "@type": "FAQPage", mainEntity: [
     { "@type": "Question", name: "Do you offer emergency callouts at night?" }] })),
     "Do you offer emergency callouts at night? Yes we do.", "static"), "ld-faq-invisible"));

ok("an article page with no Article block is reported",
   has(S.judgeSchema(S.parseLd(LD({ "@type": "Organization" })), "", "editorial"),
       "ld-no-article"));
ok("a static page is not expected to carry an Article block",
   !has(S.judgeSchema(S.parseLd(LD({ "@type": "Organization" })), "", "static"),
        "ld-no-article"));
ok("a page with no schema at all produces no schema findings beyond the missing one",
   S.judgeSchema([], "", "static").length === 0,
   "judgePage already reports the absence");

ok("no Organization anywhere on the site is a major finding",
   sevOf(S.judgeSchemaCoverage(["WebSite"], 3), "ld-no-org") === "MAJOR");
ok("LocalBusiness satisfies the Organization requirement",
   !has(S.judgeSchemaCoverage(["LocalBusiness", "WebSite"], 0), "ld-no-org"));
ok("no BreadcrumbList with inner pages present is reported",
   has(S.judgeSchemaCoverage(["Organization", "WebSite"], 4), "ld-no-breadcrumb"));
ok("a site with no inner pages is not asked for breadcrumbs",
   !has(S.judgeSchemaCoverage(["Organization", "WebSite"], 0), "ld-no-breadcrumb"));

// ------------------------------------------------------------ content

const page = (over) => Object.assign({
  url: "https://x.test/services/plumbing", ok: true, title: "Plumbing in Leeds",
  kind: "other", bodyText: "", }, over || {});
const prose = (n) => ("we repair taps showers boilers and blocked drains across "
  + "the city with a qualified engineer on call every day of the week ").repeat(n);

ok("a page under 300 words is reported as thin",
   has(S.judgeContent(page({ bodyText: prose(2) })), "thin-content"));
ok("a page of normal length is not",
   !has(S.judgeContent(page({ bodyText: prose(30) })), "thin-content"));
ok("a contact page is not judged for thinness",
   !has(S.judgeContent(page({ url: "https://x.test/contact", bodyText: prose(2) })),
        "thin-content"),
   "it is not meant to rank on word count");
ok("a blog index is not judged for thinness",
   !has(S.judgeContent(page({ kind: "hub", bodyText: prose(2) })), "thin-content"));

ok("ordinary prose is not reported as stuffed",
   !has(S.judgeContent(page({ bodyText: prose(40) })), "keyword-stuffing"),
   "the check has to survive real writing");
ok("one term at over six percent is reported as stuffing",
   has(S.judgeContent(page({ bodyText: prose(20) + "plumber ".repeat(90) })),
       "keyword-stuffing"));
ok("the stuffing finding names the term and the share",
   /"plumber" is \d+\.\d% of the words/.test(
     S.judgeContent(page({ bodyText: prose(20) + "plumber ".repeat(90) }))
       .find((f) => f.id === "keyword-stuffing").title));
ok("density is not judged on a short page at all",
   !S.judgeContent(page({ bodyText: "plumber plumber plumber" }))
     .some((f) => f.id === "keyword-stuffing" || f.id === "keyword-density"),
   "three words cannot have a density");

// A collapsed menu is hidden and links inward. An injection is hidden, sits
// outside any interface component, and links out. Measured on a real docs
// site: the first version called 191 words in 6 collapsed nav panels a blocker.
const menu = page({ bodyText: prose(30),
  hiddenText: { words: 191, nodes: 6, links: 43, external: 0, internal: 43,
                sample: "Home Docs Blog About Learn Patterns" } });
ok("a collapsed menu full of internal links is not reported",
   !has(S.judgeContent(menu), "hidden-text"),
   "every dropdown on the web looks like this");

const injected = page({ bodyText: prose(30),
  hiddenText: { words: 160, nodes: 2, links: 30, external: 30, internal: 0,
                sample: "cheap viagra online casino bonus replica watch" } });
ok("hidden text linking off-site to a spam vertical is a blocker",
   sevOf(S.judgeContent(injected), "hidden-text") === "BLOCKER");
ok("and it says to treat the site as compromised",
   /compromised until proven otherwise/.test(
     S.judgeContent(injected).find((f) => f.id === "hidden-text").fix));

const offsiteOnly = page({ bodyText: prose(30),
  hiddenText: { words: 160, nodes: 2, links: 12, external: 12, internal: 0,
                sample: "some ordinary looking words here and there" } });
ok("hidden off-site links without spam wording are major, not a blocker",
   sevOf(S.judgeContent(offsiteOnly), "hidden-text") === "MAJOR",
   "suspicious, not proven");
ok("a small amount of hidden text is ignored",
   !has(S.judgeContent(page({ bodyText: prose(30),
     hiddenText: { words: 12, nodes: 1, links: 1, external: 1, internal: 0,
                   sample: "skip to content" } })), "hidden-text"));

ok("a pile of links to many outside domains is reported",
   has(S.judgeContent(page({ bodyText: prose(30),
     offsiteLinks: { count: 45, hosts: 31, sample: ["a.test", "b.test"] } })),
     "offsite-link-pile"));
ok("and it says a directory legitimately looks like that",
   /directory or a link roundup/.test(
     S.judgeContent(page({ bodyText: prose(30),
       offsiteLinks: { count: 45, hosts: 31, sample: ["a.test"] } }))
       .find((f) => f.id === "offsite-link-pile").detail));
ok("a handful of outbound links is normal",
   !has(S.judgeContent(page({ bodyText: prose(30),
     offsiteLinks: { count: 6, hosts: 4, sample: [] } })), "offsite-link-pile"));

ok("spam wording in the body but not the title is only a note",
   sevOf(S.judgeContent(page({ bodyText: prose(20) + " casino bonus " })),
         "spam-vertical-words") === "NOTE",
   "plenty of real sites use these words");
ok("and it says so rather than accusing",
   /proves nothing/.test(S.judgeContent(page({ bodyText: prose(20) + " casino " }))
     .find((f) => f.id === "spam-vertical-words").detail));
ok("a real casino site is not flagged for its own subject",
   !has(S.judgeContent(page({ title: "Casino reviews",
     bodyText: prose(20) + " casino " })), "spam-vertical-words"));

// ------------------------------------------------------------------ NAP

const napPage = (url, tel, ld) => ({ url, ok: true, telLinks: tel || [],
                                     ldBlocks: S.parseLd(ld || "") });

ok("the same number written two ways is one number",
   S.phoneKey("+44 (113) 496-0000") === S.phoneKey("01134960000"),
   "formatting must not create a false inconsistency");
ok("a string too short to be a number is ignored", S.phoneKey("12") === "");

ok("one number across the site is clean",
   S.judgeNap([napPage("/a", ["0113 496 0000"]),
               napPage("/b", ["+44 113 496 0000"])]).length === 0);
const twoNums = S.judgeNap([napPage("/a", ["0113 496 0000"]),
                            napPage("/b", ["0113 496 9999"])]);
ok("two different numbers across the site is reported",
   has(twoNums, "nap-phone-inconsistent"));
ok("and it says a second number can be legitimate",
   /confirm with the client rather than picking one/
     .test(twoNums.find((f) => f.id === "nap-phone-inconsistent").detail),
   "a fax or a department line");
ok("the finding counts how many pages each number is on",
   /\(1 page\(s\)\)/.test(twoNums.find((f) => f.id === "nap-phone-inconsistent").detail));

const mismatch = S.judgeNap([napPage("/a", ["0113 496 0000"],
  LD({ "@type": "LocalBusiness", name: "Bright", telephone: "0113 496 7777",
       address: { "@type": "PostalAddress", postalCode: "LS1" } }))]);
ok("schema telephone that matches nothing on the page is reported",
   has(mismatch, "nap-schema-phone"));
ok("and it says disagreeing schema is worse than none",
   /worse than no\s+schema/.test(
     mismatch.find((f) => f.id === "nap-schema-phone").detail));
ok("schema that agrees with the page is not reported",
   !has(S.judgeNap([napPage("/a", ["0113 496 0000"],
     LD({ "@type": "LocalBusiness", name: "Bright", telephone: "+441134960000",
          address: {} }))]), "nap-schema-phone"),
   "the same number in another format");
ok("two different business names in schema are reported",
   has(S.judgeNap([napPage("/a", ["0113 496 0000"],
     LD({ "@type": "LocalBusiness", name: "Bright Dental", telephone: "0113 496 0000", address: {} })
     + LD({ "@type": "Organization", name: "Bright Dental Ltd", telephone: "0113 496 0000" }))]),
     "nap-schema-name"));
ok("local schema with a phone and no address is reported",
   has(S.judgeNap([napPage("/a", ["0113 496 0000"],
     LD({ "@type": "LocalBusiness", name: "Bright", telephone: "0113 496 0000" }))]),
     "nap-no-address"));
ok("a site with no phone numbers produces no NAP findings",
   S.judgeNap([napPage("/a", [])]).length === 0,
   "absence is not inconsistency");
ok("no pages at all is handled", S.judgeNap([]).length === 0);

// -------------------------------------------------- internal linking

ok("a blog post is an editorial page", S.pageKind("https://x.test/blog/a-post/") === "editorial");
ok("a dated permalink is editorial too",
   S.pageKind("https://x.test/2026/08/05/a-post/") === "editorial");
ok("the blog index is a hub, not an article",
   S.pageKind("https://x.test/blog/") === "hub",
   "an archive is never a link source");
ok("a service page is static", S.pageKind("https://x.test/services/plumbing/") === "static");
ok("the home page is static", S.pageKind("https://x.test/") === "static");
ok("an unrecognised path is neither", S.pageKind("https://x.test/whatever/") === "other");
ok("the silo is the first path segment", S.siloOf("https://x.test/learn/x/") === "learn");
ok("the root has its own silo", S.siloOf("https://x.test/") === "(root)");

const mkPage = (url, anchors) => ({ url, ok: true, anchors: anchors || [] });
const g = S.buildGraph([
  mkPage("https://x.test/blog/one", [
    { href: "https://x.test/services/plumbing", text: "emergency plumbing", nav: false },
    { href: "https://x.test/contact", text: "click here", nav: false }]),
  mkPage("https://x.test/services/plumbing", [
    { href: "https://x.test/blog/one", text: "our guide", nav: true }]),
  mkPage("https://x.test/orphan", []),
]);
ok("the graph counts inbound links", g.get("https://x.test/services/plumbing").inbound === 1);
ok("it separates in-content links from navigation",
   g.get("https://x.test/blog/one").inbound === 1
   && g.get("https://x.test/blog/one").inContent === 0,
   "a nav link is not editorial support");
ok("it counts a page's own outgoing in-content links",
   g.get("https://x.test/blog/one").outContent === 2);

const pagesForGraph = [mkPage("https://x.test/blog/one"), mkPage("https://x.test/services/plumbing"),
                       mkPage("https://x.test/orphan")];
const full = S.judgeInternalLinking(g, pagesForGraph, 1);
ok("a page nothing links to is reported when the crawl is complete",
   has(full, "orphans"), (full.find((f) => f.id === "orphans") || {}).detail);
ok("an article with fewer than three in-content links is reported",
   has(full, "thin-internal-links"));
ok("a non-descriptive anchor is reported", has(full, "anchor-vague"));
ok("and it names the offending text",
   /click here/i.test((full.find((f) => f.id === "anchor-vague") || {}).detail));

const partial = S.judgeInternalLinking(g, pagesForGraph, 0.4);
ok("orphans are NOT claimed from a partial crawl",
   !has(partial, "orphans") && has(partial, "orphans-unknown"),
   "a page linked from an unread page would look orphaned");
ok("and the report says what is needed to count them",
   /Raise --pages/.test((partial.find((f) => f.id === "orphans-unknown") || {}).detail));

// Measured on a live site: with no readable sitemap, coverage defaulted to 1
// and the orphan count was stated as fact on that basis.
const noSitemap = S.judgeInternalLinking(g, pagesForGraph, null);
ok("orphans are NOT claimed when there is no sitemap at all",
   !has(noSitemap, "orphans") && has(noSitemap, "orphans-unknown"),
   "unknown coverage is not complete coverage");
ok("and the reason given is the missing sitemap, not a percentage",
   /no readable sitemap/.test((noSitemap.find((f) => f.id === "orphans-unknown") || {}).detail));

const repeated = S.buildGraph(Array.from({ length: 6 }, (_, i) =>
  mkPage("https://x.test/blog/p" + i, [
    { href: "https://x.test/services/x", text: "best plumber leeds", nav: false },
    { href: "https://x.test/a", text: "one", nav: false },
    { href: "https://x.test/b", text: "two", nav: false }])));
const rep = S.judgeInternalLinking(repeated,
  Array.from({ length: 6 }, (_, i) => mkPage("https://x.test/blog/p" + i)), 1);
ok("the same exact-match anchor across six pages is reported",
   has(rep, "anchor-repetition"),
   (rep.find((f) => f.id === "anchor-repetition") || {}).detail);

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
