/**
 * The numbers seo-complete demands, measured.
 *
 *   node seo.js <url> [--out <dir>] [--pages 25] [--max-links 50] [--no-links]
 *
 * Reads the **raw** HTML for everything that must be server-rendered, and the
 * **rendered** DOM for what a visitor sees. Those are different questions and
 * one fetch cannot answer both: a JSON-LD block injected after hydration is
 * invisible to a crawler and perfectly visible in the DOM.
 *
 * The soft-404 check runs first and changes how everything after it is read.
 * A single-page app answers 200 with its own shell for every unknown path, so
 * on such a site a broken internal link **also** answers 200 and a status-code
 * link check reports a clean site that is full of dead links. When that is
 * detected the link results are marked unreliable-by-status and compared
 * against the shell instead, and the report says so. Trusting the status code
 * here is the same mistake as trusting it for `/.env`, which this workspace
 * has already made once with robots.txt.
 */
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

function loadPlaywright() {
  try { return require("playwright"); } catch { /* keep looking */ }
  const roots = [process.env.NODE_PATH];
  try { roots.push(execSync("npm root -g", { encoding: "utf8" }).trim()); } catch { /* ignore */ }
  roots.push(path.join(process.env.APPDATA || "", "npm", "node_modules"));
  for (const r of roots) {
    if (r && fs.existsSync(path.join(r, "playwright"))) return require(path.join(r, "playwright"));
  }
  console.error("playwright not found; it is installed globally here and a bare\n" +
                "require() does not resolve a global module.");
  process.exit(2);
}

const LIMITS = { title: 60, description: 160, descriptionMin: 150, h1: 60 };
// The crawlers that decide whether a site can be quoted in an AI answer.
// Blocking them leaves Google search untouched, so nothing in the client's
// search reporting ever shows it.
const AI_AGENTS = ["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended",
                   "Bytespider"];
const SEV_RANK = { BLOCKER: 0, MAJOR: 1, MINOR: 2, NOTE: 3 };
const SUPERLATIVE = /\b(best|top|leading|no\.?\s*1|number one|cheapest|ultimate)\b/i;

/** Never "Not Found" or "N/A": those read as findings and get fixed. */
const MISSING = "Missing";

/** A development origin, where the address-variant checks do not apply. */
function isDevHost(u) {
  let h;
  try { h = new URL(u).hostname.toLowerCase(); } catch { return false; }
  if (h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "::1") return true;
  return /\.(?:localhost|test|local|internal)$/.test(h);
}

/**
 * An entity that survived into a plain-text field.
 *
 * The value is already decoded by the parser, so `&amp;` still being here means
 * the source was double-encoded and the page renders the five literal
 * characters. That reached a client screenshot once.
 */
function entityLeak(text) {
  return /&(?:amp|nbsp|rsquo|lsquo|quot|apos|lt|gt|#\d{2,4}|#x[0-9a-f]{2,4});/i
    .test(String(text || ""));
}

function judgeTitle(title, h1) {
  const out = [];
  const t = String(title || "");
  if (!t) {
    out.push({ sev: "MAJOR", id: "title-missing", title: "Title is " + MISSING });
    return out;
  }
  if (t.length > LIMITS.title) {
    out.push({ sev: "MAJOR", id: "title-long",
               title: "Title is " + t.length + " characters, over " + LIMITS.title });
  }
  if (entityLeak(t)) {
    out.push({ sev: "MAJOR", id: "title-entity",
               title: "Title renders an HTML entity as literal text" });
  }
  // One separator reads; a title chopped into four segments does not.
  const seps = (t.match(/[|–—-]/g) || []).length;
  if (seps > 2) {
    out.push({ sev: "MINOR", id: "title-separators",
               title: "Title is split by " + seps + " separators" });
  }
  if (SUPERLATIVE.test(t)) {
    out.push({ sev: "MINOR", id: "title-superlative",
               title: "Title uses a superlative, which Google rewrites",
               detail: "Then the title you wrote is not the title anyone sees." });
  }
  if (h1 && t && firstWords(t, 3) && firstWords(t, 3) === firstWords(h1, 3)) {
    // aligned - nothing to say
  } else if (h1) {
    out.push({ sev: "NOTE", id: "title-h1-drift",
               title: "Title and H1 do not open with the same words",
               detail: "The closer they are, the less Google rewrites the title." });
  }
  return out;
}

function firstWords(s, n) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/).filter(Boolean).slice(0, n).join(" ");
}

function judgeDescription(desc) {
  const out = [];
  const d = String(desc || "");
  if (!d) {
    out.push({ sev: "MAJOR", id: "desc-missing",
               title: "Meta description is " + MISSING });
    return out;
  }
  if (d.length > LIMITS.description) {
    out.push({ sev: "MAJOR", id: "desc-long",
               title: "Meta description is " + d.length + " characters, over "
                    + LIMITS.description });
  } else if (d.length < LIMITS.descriptionMin) {
    out.push({ sev: "NOTE", id: "desc-short",
               title: "Meta description is " + d.length + " characters",
               detail: "The band worth aiming for is " + LIMITS.descriptionMin
                     + " to " + LIMITS.description + "." });
  }
  if (entityLeak(d)) {
    out.push({ sev: "MAJOR", id: "desc-entity",
               title: "Meta description renders an HTML entity as literal text" });
  }
  return out;
}

function judgeH1(h1s) {
  const out = [];
  const list = h1s || [];
  if (!list.length) {
    out.push({ sev: "MAJOR", id: "h1-missing", title: "H1 is " + MISSING });
    return out;
  }
  if (list.length > 1) {
    out.push({ sev: "MAJOR", id: "h1-multiple",
               title: list.length + " H1 tags on one page" });
  }
  if (list[0] && list[0].length > LIMITS.h1) {
    out.push({ sev: "MINOR", id: "h1-long",
               title: "H1 is " + list[0].length + " characters, over " + LIMITS.h1 });
  }
  if (entityLeak(list[0])) {
    out.push({ sev: "MAJOR", id: "h1-entity",
               title: "H1 renders an HTML entity as literal text" });
  }
  return out;
}

/**
 * The four addresses a site answers on. Exactly one may end at 200.
 *
 * Two variants both answering 200 is a duplicate-content defect, and it is the
 * one nobody notices because each variant looks fine on its own.
 */
function judgeVariants(results) {
  const out = [];
  const live = results.filter((r) => r.status === 200);
  const finals = new Set(live.map((r) => String(r.final || "").replace(/\/$/, "")));
  if (!live.length) {
    out.push({ sev: "BLOCKER", id: "no-variant-200",
               title: "No address variant answered 200",
               detail: results.map((r) => r.url + " -> " + (r.status || "no answer"))
                 .join("; ") });
    return out;
  }
  if (finals.size > 1) {
    out.push({ sev: "BLOCKER", id: "duplicate-variants",
               title: finals.size + " different addresses serve the site",
               detail: Array.from(finals).join(" and ")
                     + " - duplicate content, and each one looks fine alone.",
               fix: "301 every variant to one canonical address." });
  }
  for (const r of results) {
    if (r.scheme === "http" && r.status === 200 && !/^https:/.test(r.final || "")) {
      out.push({ sev: "BLOCKER", id: "http-no-redirect",
                 title: r.url + " serves over http without redirecting" });
    }
  }
  return out;
}

/** The canonical on each variant has to point at the same single address. */
function judgeCanonical(pages) {
  const out = [];
  const withPage = pages.filter((p) => p.ok);
  const missing = withPage.filter((p) => !p.canonical);
  if (missing.length) {
    out.push({ sev: "MAJOR", id: "canonical-missing",
               title: missing.length + " page(s) have no rel=canonical",
               detail: missing.slice(0, 5).map((p) => p.url).join(", ") });
  }
  const set = new Set(withPage.map((p) => p.canonical).filter(Boolean)
    .map((c) => c.replace(/\/$/, "")));
  if (set.size > 1 && withPage.length > 1 && withPage.every((p) => p.isVariant)) {
    out.push({ sev: "MAJOR", id: "canonical-inconsistent",
               title: "The address variants disagree about the canonical",
               detail: Array.from(set).join(" vs ") });
  }
  for (const p of withPage) {
    if (p.ogUrl && p.canonical &&
        p.ogUrl.replace(/\/$/, "") !== p.canonical.replace(/\/$/, "")) {
      out.push({ sev: "MINOR", id: "og-url-mismatch",
                 title: "og:url does not match the canonical on " + p.url });
      break;
    }
  }
  return out;
}

/** Is the site blocking the crawlers that decide whether it can be quoted? */
function judgeRobots(body, status) {
  const out = [];
  if (status === 404 || !body) {
    return [{ sev: "MINOR", id: "robots-missing",
              title: "robots.txt is " + MISSING,
              detail: "Not fatal - everything is allowed by default - but the "
                    + "sitemap cannot be declared." }];
  }
  const lines = String(body).split(/\r?\n/).map((l) => l.trim())
    .filter((l) => l && !l.startsWith("#"));
  let agent = null;
  const blocked = {};
  let starBlocksAll = false;
  for (const line of lines) {
    const ua = line.match(/^user-agent\s*:\s*(.+)$/i);
    if (ua) { agent = ua[1].trim(); continue; }
    const dis = line.match(/^disallow\s*:\s*(.*)$/i);
    if (dis && agent) {
      const rule = dis[1].trim();
      if (rule === "/") {
        if (agent === "*") starBlocksAll = true;
        else blocked[agent.toLowerCase()] = true;
      }
    }
  }
  const named = lines.filter((l) => /^user-agent/i.test(l))
    .map((l) => l.split(":").slice(1).join(":").trim().toLowerCase());
  const hit = AI_AGENTS.filter((a) => blocked[a.toLowerCase()]);
  if (hit.length) {
    out.push({ sev: "MAJOR", id: "ai-blocked",
               title: "robots.txt blocks " + hit.join(", "),
               detail: "The site cannot appear in AI answers. Google search is "
                     + "untouched, so nothing in the client's search reporting "
                     + "shows this. Confirm it was a decision." });
  } else if (starBlocksAll && !AI_AGENTS.some((a) => named.includes(a.toLowerCase()))) {
    out.push({ sev: "MAJOR", id: "all-blocked",
               title: "robots.txt disallows everything for every crawler",
               detail: "User-agent: * with Disallow: / and no exceptions." });
  }
  if (!/^sitemap\s*:/im.test(String(body))) {
    out.push({ sev: "MINOR", id: "robots-no-sitemap",
               title: "robots.txt declares no sitemap" });
  }
  return out;
}

/**
 * Does an address that cannot exist return a real 404?
 *
 * This runs first because its answer changes how every link result below is
 * read. Status 200 for a path that cannot exist means the app answers for
 * everything, so no link check by status code can be believed on this site.
 */
function judge404(status, body, shell) {
  if (status === 404) return { findings: [], softs: false };
  if (status >= 500) {
    return { findings: [{ sev: "MAJOR", id: "404-server-error",
                          title: "An invalid URL returns " + status
                               + " instead of 404" }], softs: false };
  }
  if (status === 200) {
    const same = shell && body && similar(body, shell);
    return {
      findings: [{ sev: "MAJOR", id: "soft-404",
                   title: "An invalid URL returns 200, not 404",
                   detail: (same ? "It serves the same shell as the home page. "
                                 : "")
                         + "Search engines index unlimited soft 404s and a "
                         + "genuinely missing page never reports itself.",
                   fix: "Return status 404 for unmatched routes." }],
      softs: true,
    };
  }
  return { findings: [{ sev: "NOTE", id: "404-odd",
                        title: "An invalid URL returns " + status }], softs: false };
}

/** Crude but adequate: are two documents essentially the same shell? */
function similar(a, b) {
  const norm = (s) => String(s || "").replace(/\s+/g, " ").slice(0, 4000);
  const x = norm(a), y = norm(b);
  if (!x || !y) return false;
  if (Math.abs(x.length - y.length) > Math.max(x.length, y.length) * 0.25) return false;
  let same = 0;
  for (let i = 0; i < Math.min(x.length, y.length); i += 1) {
    if (x[i] === y[i]) same += 1;
  }
  return same / Math.min(x.length, y.length) > 0.85;
}

/**
 * One link's verdict. A refusal is not a broken page.
 *
 * A 403 or a 429 says something about who is asking, not about whether the
 * page exists, and folding those into the broken count sends somebody to fix
 * pages that are fine.
 */
function classifyLink(status, softs) {
  if (status === 200) return softs ? "unverifiable" : "ok";
  if (status >= 300 && status < 400) return "redirect";
  if (status === 403 || status === 429) return "blocked";
  if (status === 404 || status === 410) return "broken";
  if (status >= 500) return "error";
  return "odd";
}

function judgeLinks(links, softs) {
  const out = [];
  const by = (k) => links.filter((l) => l.verdict === k);
  const broken = by("broken"), err = by("error"), red = by("redirect"),
        blocked = by("blocked");
  if (softs) {
    out.push({ sev: "MAJOR", id: "links-unverifiable",
               title: "Internal links cannot be checked by status code here",
               detail: "The site answers 200 for paths that do not exist, so a "
                     + "broken link answers 200 too. Fix the soft 404 first, "
                     + "then re-run; until then this count means nothing." });
    return out;
  }
  if (broken.length) {
    out.push({ sev: "BLOCKER", id: "links-broken",
               title: broken.length + " internal link(s) do not resolve",
               detail: broken.slice(0, 8)
                 .map((l) => l.url + " (on " + l.foundOn + ")").join("; "),
               fix: "Point them at a real page or remove them." });
  }
  if (err.length) {
    out.push({ sev: "MAJOR", id: "links-error",
               title: err.length + " internal link(s) return a server error",
               detail: err.slice(0, 5).map((l) => l.url).join("; ") });
  }
  if (red.length) {
    out.push({ sev: "MINOR", id: "links-redirect",
               title: red.length + " internal link(s) go through a redirect",
               detail: "Avoidable, not an error: author the live URL so every "
                     + "page does not pay a hop." });
  }
  if (blocked.length) {
    out.push({ sev: "NOTE", id: "links-blocked",
               title: blocked.length + " link(s) refused us (403 or 429)",
               detail: "A refusal is about who is asking, not whether the page "
                     + "exists. Not counted as broken." });
  }
  return out;
}

function judgeSitemap(sm) {
  const out = [];
  if (!sm || !sm.ok) {
    out.push({ sev: "MAJOR", id: "sitemap-missing",
               title: "sitemap.xml is " + MISSING });
    return out;
  }
  if (sm.duplicates) {
    out.push({ sev: "MAJOR", id: "sitemap-duplicates",
               title: sm.duplicates + " duplicate URL(s) in the sitemap" });
  }
  if (sm.redirecting && sm.redirecting.length) {
    out.push({ sev: "MAJOR", id: "sitemap-redirects",
               title: sm.redirecting.length + " sitemap URL(s) redirect",
               detail: "They are correct as redirects; listing them is the "
                     + "error. " + sm.redirecting.slice(0, 5).join(", ") });
  }
  if (!sm.count) {
    out.push({ sev: "MAJOR", id: "sitemap-empty", title: "The sitemap lists no URLs" });
  }
  return out;
}

function judgePage(p) {
  const out = [];
  if (!p.ok) return out;
  out.push(...judgeTitle(p.title, (p.h1 || [])[0]));
  out.push(...judgeDescription(p.description));
  out.push(...judgeH1(p.h1));
  if (!p.rawJsonLd) {
    out.push({ sev: "MAJOR", id: "jsonld-not-server-rendered",
               title: "No JSON-LD in the raw HTML",
               detail: p.domJsonLd
                 ? "There is a block in the rendered DOM, so it is injected "
                 + "after hydration and a crawler never sees it."
                 : "No structured data at all." });
  }
  if (p.noindex) {
    out.push({ sev: "BLOCKER", id: "noindex",
               title: "Page is noindexed",
               detail: "Set by " + p.noindexFrom + ". A staging flag that "
                     + "survived a launch looks exactly like this." });
  }
  if (p.imagesNoAlt) {
    out.push({ sev: "MINOR", id: "img-alt",
               title: p.imagesNoAlt + " image(s) with no alt attribute" });
  }
  if (p.altEntities) {
    out.push({ sev: "MINOR", id: "alt-entity",
               title: p.altEntities + " image alt(s) render an HTML entity" });
  }
  if (!p.og) {
    out.push({ sev: "MINOR", id: "og-missing",
               title: "Open Graph tags are " + MISSING });
  }
  if (!p.twitter) {
    out.push({ sev: "NOTE", id: "twitter-missing",
               title: "twitter:card is " + MISSING });
  }
  for (const f of out) f.where = p.url;
  return out;
}

function sortFindings(list) {
  return list.slice().sort((a, b) =>
    (SEV_RANK[a.sev] ?? 9) - (SEV_RANK[b.sev] ?? 9) ||
    String(a.title).localeCompare(String(b.title)));
}

function report(data) {
  const f = sortFindings(data.findings || []);
  const n = (s) => f.filter((x) => x.sev === s).length;
  const L = ["# SEO pass - " + data.url, ""];
  L.push("Read " + (data.pagesRead || 0) + " page(s), checked "
         + (data.linksChecked || 0) + " internal link(s). " + f.length
         + " finding(s): " + n("BLOCKER") + " blocker, " + n("MAJOR")
         + " major, " + n("MINOR") + " minor, " + n("NOTE") + " note.");
  L.push("");
  if (data.softs) {
    L.push("**This site answers 200 for paths that do not exist.** Every link "
           + "result below is unreliable until that is fixed, because a broken "
           + "link answers 200 as well.");
    L.push("");
  }
  if (!f.length) L.push("Nothing found by these checks.");
  for (const x of f) {
    L.push("## " + x.sev + " - " + x.title);
    if (x.where) L.push("On: " + x.where);
    if (x.detail) L.push(x.detail);
    if (x.fix) L.push("Fix: " + x.fix);
    L.push("");
  }
  L.push("## The numbers");
  const c = data.counts || {};
  for (const [k, v] of Object.entries(c)) L.push("  " + k + ": " + v);
  L.push("");
  L.push("## Limits");
  L.push("Raw HTML was read for what must be server-rendered and the rendered "
         + "DOM for what a visitor sees. Link checking is capped at "
         + (data.linkCap || 0) + " and prioritises navigation, footer and "
         + "in-content links"
         + (data.linkCapHit ? " - the cap was reached, so this is not the whole site."
                            : "."));
  L.push("A 403 or 429 is reported as blocked, never as broken. A value that "
         + "could not be read is reported as Missing, never as Not Found.");
  return L.join("\n");
}

// --------------------------------------------------------------- the run

async function readPage(ctx, page, url, opts) {
  const res = { url, ok: false };
  let raw = "";
  try {
    const r = await ctx.request.get(url, { timeout: 25000, maxRedirects: 5 });
    res.status = r.status();
    res.final = r.url();
    raw = await r.text();
  } catch (e) {
    res.error = String(e && e.message || e).slice(0, 120);
    return res;
  }
  if (res.status !== 200) return res;
  res.ok = true;
  // Raw HTML: the only place to answer "would a crawler see this".
  res.rawJsonLd = /<script[^>]+type\s*=\s*["']application\/ld\+json["'][^>]*>/i.test(raw);
  const xr = /<meta[^>]+name=["']robots["'][^>]*>/i.exec(raw);
  res.rawRobotsMeta = xr ? xr[0] : "";

  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 40000 });
  } catch {
    return res;
  }
  const dom = await page.evaluate(() => {
    const at = (sel, attr) => {
      const e = document.querySelector(sel);
      return e ? (e.getAttribute(attr) || "") : "";
    };
    const imgs = Array.from(document.querySelectorAll("img"));
    return {
      title: document.title || "",
      description: at('meta[name="description"]', "content"),
      canonical: at('link[rel="canonical"]', "href"),
      ogUrl: at('meta[property="og:url"]', "content"),
      og: !!document.querySelector('meta[property^="og:"]'),
      twitter: !!document.querySelector('meta[name^="twitter:"]'),
      robotsMeta: at('meta[name="robots"]', "content"),
      hreflang: document.querySelectorAll('link[rel="alternate"][hreflang]').length,
      h1: Array.from(document.querySelectorAll("h1")).map((h) => (h.textContent || "").trim()),
      domJsonLd: !!document.querySelector('script[type="application/ld+json"]'),
      breadcrumb: /BreadcrumbList/.test(
        Array.from(document.querySelectorAll('script[type="application/ld+json"]'))
          .map((s) => s.textContent || "").join(" ")),
      imagesNoAlt: imgs.filter((i) => !i.hasAttribute("alt")).length,
      alts: imgs.map((i) => i.getAttribute("alt") || ""),
      links: Array.from(document.querySelectorAll("a[href]"))
        .map((a) => ({ href: a.href, nav: !!a.closest("nav,header,footer") })),
    };
  });
  Object.assign(res, dom);
  res.altEntities = (dom.alts || []).filter(entityLeak).length;
  const meta = String(dom.robotsMeta || "");
  res.noindex = /noindex/i.test(meta);
  res.noindexFrom = res.noindex ? "the robots meta tag" : "";
  return res;
}

async function run(url, opts) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ ignoreHTTPSErrors: true });
  const page = await ctx.newPage();
  const findings = [];
  const target = new URL(url);
  const host = target.hostname.replace(/^www\./, "");

  // 1. The addresses the site answers on.
  //
  // The www pair only exists for a real domain name. `https://www.127.0.0.1/`
  // is not a URL at all - Node rejects it outright - and a www form of an IP
  // address or of localhost means nothing. The port has to be carried through
  // too, or a dev server on :5173 gets probed on :443.
  const port = target.port ? ":" + target.port : "";
  const bare = host + port;
  const isName = /^[a-z0-9-]+(\.[a-z0-9-]+)+$/i.test(host)
    && !/^\d{1,3}(\.\d{1,3}){3}$/.test(host);
  const wanted = ["https://" + bare + "/", "http://" + bare + "/"];
  if (isName) wanted.push("https://www." + bare + "/", "http://www." + bare + "/");

  const variants = [];
  for (const u of wanted) {
    let rec;
    try { rec = { url: u, scheme: new URL(u).protocol.replace(":", "") }; }
    catch { continue; }
    try {
      const r = await ctx.request.get(u, { timeout: 20000, maxRedirects: 5 });
      rec.status = r.status();
      rec.final = r.url();
    } catch (e) { rec.error = String(e && e.message || e).slice(0, 80); }
    variants.push(rec);
  }
  // On a development origin the transport checks do not apply, the same rule
  // security.js follows: http on localhost is expected, not a defect, and
  // reporting it trains people to skip the whole report.
  if (!isDevHost(url)) findings.push(...judgeVariants(variants));

  // 2. robots.txt
  let robotsBody = "", robotsStatus = 0;
  try {
    const r = await ctx.request.get(target.origin + "/robots.txt", { timeout: 20000 });
    robotsStatus = r.status();
    robotsBody = r.status() === 200 ? await r.text() : "";
  } catch { /* reported as missing */ }
  findings.push(...judgeRobots(robotsBody, robotsStatus));

  // 3. The soft-404 test, before anything that reads a status code.
  const home = await ctx.request.get(target.origin + "/", { timeout: 20000 })
    .then((r) => r.text()).catch(() => "");
  let softs = false;
  try {
    const bogus = target.origin + "/a-path-that-cannot-exist-" + Date.now();
    const r = await ctx.request.get(bogus, { timeout: 20000, maxRedirects: 3 });
    const v = judge404(r.status(), await r.text().catch(() => ""), home);
    findings.push(...v.findings);
    softs = v.softs;
  } catch { /* a refusal here is fine */ }

  // 4. The sitemap.
  const smUrl = (robotsBody.match(/^sitemap\s*:\s*(\S+)/im) || [])[1]
    || target.origin + "/sitemap.xml";
  const sm = { ok: false, count: 0, urls: [] };
  try {
    const r = await ctx.request.get(smUrl, { timeout: 25000, maxRedirects: 3 });
    if (r.status() === 200) {
      let xml = await r.text();
      let locs = Array.from(xml.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/gi)).map((m) => m[1]);
      // A sitemap index points at more sitemaps; follow a few.
      if (/<sitemapindex/i.test(xml)) {
        const kids = locs.slice(0, 5);
        locs = [];
        for (const k of kids) {
          try {
            const kr = await ctx.request.get(k, { timeout: 25000 });
            if (kr.status() === 200) {
              const kx = await kr.text();
              locs.push(...Array.from(kx.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/gi))
                .map((m) => m[1]));
            }
          } catch { /* skip one child */ }
        }
        sm.index = true;
        sm.children = kids.length;
      }
      sm.ok = true;
      sm.urls = locs;
      sm.count = new Set(locs).size;
      sm.duplicates = locs.length - sm.count;
    }
  } catch { /* reported as missing */ }

  // Do any sitemap URLs redirect? A sample, not all of them.
  sm.redirecting = [];
  for (const u of (sm.urls || []).slice(0, 10)) {
    try {
      const r = await ctx.request.get(u, { timeout: 15000, maxRedirects: 0 });
      if (r.status() >= 300 && r.status() < 400) sm.redirecting.push(u);
    } catch { /* ignore */ }
  }
  findings.push(...judgeSitemap(sm));

  // 5. Pages: the sitemap's if there is one, else the home page's own links.
  let pageUrls = (sm.urls || []).filter((u) => {
    try { return new URL(u).hostname.replace(/^www\./, "") === host; }
    catch { return false; }
  });
  if (!pageUrls.length) pageUrls = [target.origin + "/"];
  pageUrls = Array.from(new Set(pageUrls)).slice(0, opts.pages);

  const pages = [];
  for (const u of pageUrls) {
    pages.push(await readPage(ctx, page, u, opts));
  }
  for (const p of pages) findings.push(...judgePage(p));
  findings.push(...judgeCanonical(pages));

  // Duplicate titles and descriptions across the set.
  const dupe = (field) => {
    const seen = {};
    for (const p of pages) {
      const v = (p[field] || "").trim();
      if (!v) continue;
      seen[v] = (seen[v] || 0) + 1;
    }
    return Object.entries(seen).filter(([, n]) => n > 1);
  };
  for (const [field, label] of [["title", "title"], ["description", "meta description"]]) {
    const d = dupe(field);
    if (d.length) {
      findings.push({ sev: "MAJOR", id: "dupe-" + field,
                      title: d.length + " " + label + "(s) are used on more than one page",
                      detail: d.slice(0, 3).map(([v, n]) => '"' + v.slice(0, 48) + '" x' + n)
                        .join("; ") });
    }
  }

  // 6. Internal links.
  let linksChecked = 0, linkCapHit = false;
  const linkRows = [];
  if (opts.links) {
    const seen = new Map();
    for (const p of pages) {
      for (const l of (p.links || [])) {
        let h;
        try { h = new URL(l.href); } catch { continue; }
        if (h.hostname.replace(/^www\./, "") !== host) continue;
        if (!/^https?:$/.test(h.protocol)) continue;
        const key = h.origin + h.pathname;
        if (!seen.has(key)) seen.set(key, { url: key, foundOn: p.url, nav: l.nav });
      }
    }
    // Navigation, footer and in-content links first, so a cap cuts the tail.
    const ordered = Array.from(seen.values())
      .sort((a, b) => (b.nav ? 1 : 0) - (a.nav ? 1 : 0));
    linkCapHit = ordered.length > opts.maxLinks;
    for (const l of ordered.slice(0, opts.maxLinks)) {
      try {
        const r = await ctx.request.get(l.url, { timeout: 15000, maxRedirects: 0 });
        l.status = r.status();
      } catch { l.status = 0; }
      l.verdict = classifyLink(l.status, softs);
      linkRows.push(l);
      linksChecked += 1;
    }
    findings.push(...judgeLinks(linkRows, softs));
  }

  await browser.close();

  const ok = pages.filter((p) => p.ok);
  const counts = {
    "pages read": ok.length,
    ["titles over " + LIMITS.title]:
      ok.filter((p) => (p.title || "").length > LIMITS.title).length,
    ["descriptions over " + LIMITS.description]:
      ok.filter((p) => (p.description || "").length > LIMITS.description).length,
    "pages with no H1 or more than one": ok.filter((p) => (p.h1 || []).length !== 1).length,
    "pages with no canonical": ok.filter((p) => !p.canonical).length,
    "pages with no JSON-LD in raw HTML": ok.filter((p) => !p.rawJsonLd).length,
    "plain-text fields with a literal entity":
      ok.filter((p) => entityLeak(p.title) || entityLeak(p.description)).length
      + ok.reduce((n, p) => n + (p.altEntities || 0), 0),
    "sitemap unique URLs": sm.count || 0,
    "sitemap URLs that redirect": (sm.redirecting || []).length,
    "internal links checked": linksChecked,
    "internal links broken": linkRows.filter((l) => l.verdict === "broken").length,
  };

  return {
    url, taken: new Date().toISOString().slice(0, 16).replace("T", " "),
    findings: sortFindings(findings), variants, sitemap: {
      ok: sm.ok, count: sm.count, duplicates: sm.duplicates,
      redirecting: sm.redirecting, index: !!sm.index },
    pages: ok.map((p) => ({ url: p.url, title: p.title, titleLen: (p.title || "").length,
                            description: p.description,
                            descriptionLen: (p.description || "").length,
                            h1: p.h1, canonical: p.canonical, rawJsonLd: p.rawJsonLd,
                            domJsonLd: p.domJsonLd, breadcrumb: p.breadcrumb,
                            hreflang: p.hreflang, imagesNoAlt: p.imagesNoAlt,
                            noindex: p.noindex })),
    links: linkRows, softs, counts,
    pagesRead: ok.length, linksChecked, linkCap: opts.maxLinks, linkCapHit,
  };
}

async function main() {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) {
    console.error("usage: node seo.js <url> [--out <dir>] [--pages 25] [--no-links]");
    process.exit(2);
  }
  const at = (f, d) => {
    const i = args.indexOf(f);
    return i >= 0 && args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : d;
  };
  const opts = {
    pages: parseInt(at("--pages", "25"), 10) || 25,
    maxLinks: parseInt(at("--max-links", "50"), 10) || 50,
    links: !args.includes("--no-links"),
  };
  const data = await run(url.startsWith("http") ? url : "https://" + url, opts);
  const text = report(data);
  const out = at("--out", "");
  if (out) {
    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(path.join(out, "seo.md"), text, "utf8");
    fs.writeFileSync(path.join(out, "seo.json"), JSON.stringify(data, null, 2), "utf8");
  }
  console.log(text);
  process.exit((data.findings || []).some((f) => f.sev === "BLOCKER") ? 1 : 0);
}

if (require.main === module) {
  main().catch((e) => { console.error(e); process.exit(2); });
}

module.exports = { judgeTitle, judgeDescription, judgeH1, judgeVariants, isDevHost,
                   judgeCanonical, judgeRobots, judge404, judgeLinks,
                   judgeSitemap, judgePage, classifyLink, entityLeak, similar,
                   firstWords, sortFindings, report, LIMITS, AI_AGENTS, MISSING };
