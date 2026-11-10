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
  if (h1 && !opensAlike(t, h1)) {
    out.push({ sev: "NOTE", id: "title-h1-drift",
               title: "Title and H1 do not open with the same words",
               detail: "The closer they are, the less Google rewrites the title." });
  }
  return out;
}

function wordsOf(s) {
  return String(s || "").toLowerCase().replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/).filter(Boolean);
}

function firstWords(s, n) {
  return wordsOf(s).slice(0, n).join(" ");
}

/**
 * Do a title and an H1 start the same way?
 *
 * Compared over the shorter of the two, not over a fixed three words. A
 * two-word H1 like "Contact us" can never match the first three words of
 * "Contact us - Brand", however exactly the title opens with it - which it
 * did, and the scaffold built to this system's own standards was reported as
 * drifting from them.
 */
function opensAlike(title, h1) {
  const t = wordsOf(title), h = wordsOf(h1);
  const n = Math.min(3, t.length, h.length);
  if (!n) return true;                 // nothing to compare is not a drift
  return t.slice(0, n).join(" ") === h.slice(0, n).join(" ");
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

// ------------------------------------------------------------- schema

/** Every JSON-LD block in the raw HTML, parsed. Invalid JSON is a finding. */
function parseLd(raw) {
  const out = [];
  const rx = /<script[^>]+type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
  let m;
  while ((m = rx.exec(String(raw || ""))) !== null) {
    const body = m[1].trim();
    if (!body) continue;
    try { out.push({ ok: true, json: JSON.parse(body) }); }
    catch (e) { out.push({ ok: false, error: String(e.message).slice(0, 80), body: body.slice(0, 80) }); }
  }
  return out;
}

/** One flat list of nodes, since a block may be an array or an @graph. */
function ldNodes(blocks) {
  const nodes = [];
  const walk = (v) => {
    if (Array.isArray(v)) { v.forEach(walk); return; }
    if (!v || typeof v !== "object") return;
    if (Array.isArray(v["@graph"])) { v["@graph"].forEach(walk); }
    if (v["@type"] || v["@id"]) nodes.push(v);
  };
  for (const b of blocks) if (b.ok) walk(b.json);
  return nodes;
}

const TYPES_OF = (n) => [].concat(n["@type"] || []).map(String);

// A value that was never filled in. A shipped placeholder is read by the
// client, and "[Business Name]" in a live Organization block has happened.
const PLACEHOLDER = /\[[a-z_ ]{3,30}\]|\byour[-_ ](?:business|company|brand|domain)\b|example\.com|YOUR_|lorem ipsum|\bTODO\b|xxxx/i;

/**
 * Structured data, judged for what a search engine would actually make of it.
 *
 * The `@id` check is the one worth having: a block that says
 * `publisher: {"@id": ".../#organization"}` when nothing declares that id is a
 * reference into nothing. It looks complete and resolves to no publisher.
 */
function judgeSchema(blocks, pageText, kind) {
  const out = [];
  for (const b of blocks) {
    if (!b.ok) {
      out.push({ sev: "MAJOR", id: "ld-invalid",
                 title: "A JSON-LD block is not valid JSON",
                 detail: b.error + " - near: " + b.body });
    }
  }
  const nodes = ldNodes(blocks);
  if (!nodes.length) return out;

  const counts = {};
  for (const n of nodes) for (const t of TYPES_OF(n)) counts[t] = (counts[t] || 0) + 1;
  for (const t of ["Organization", "WebSite", "LocalBusiness"]) {
    if ((counts[t] || 0) > 1) {
      out.push({ sev: "MAJOR", id: "ld-duplicate",
                 title: counts[t] + " " + t + " blocks on one page",
                 detail: "One source of truth. Two of these on a page is a "
                       + "defect, usually a template block plus an inline one." });
    }
  }

  const declared = new Set(nodes.map((n) => n["@id"]).filter(Boolean).map(String));
  const referenced = new Set();
  const collectRefs = (v) => {
    if (Array.isArray(v)) { v.forEach(collectRefs); return; }
    if (!v || typeof v !== "object") return;
    const keys = Object.keys(v);
    if (keys.length === 1 && keys[0] === "@id") { referenced.add(String(v["@id"])); return; }
    for (const k of keys) if (k !== "@id") collectRefs(v[k]);
  };
  collectRefs(nodes);
  const dangling = Array.from(referenced).filter((r) => !declared.has(r));
  if (dangling.length) {
    out.push({ sev: "MINOR", id: "ld-dangling-id",
               title: dangling.length + " @id reference(s) point at nothing on this page",
               detail: dangling.slice(0, 3).join(", ")
                     + " - it resolves only if another page declares it, and "
                     + "the block reads as complete either way." });
  }

  const flat = JSON.stringify(nodes);
  if (PLACEHOLDER.test(flat)) {
    const hit = flat.match(PLACEHOLDER);
    out.push({ sev: "MAJOR", id: "ld-placeholder",
               title: "Structured data contains an unfilled placeholder",
               detail: "Found " + JSON.stringify(hit[0]) + ". It is live and a "
                     + "validator will read it as the real value." });
  }

  for (const n of nodes) {
    if (n.serviceType && !TYPES_OF(n).includes("Service")) {
      out.push({ sev: "MINOR", id: "ld-servicetype",
                 title: "serviceType is set on " + (TYPES_OF(n)[0] || "a node")
                      + ", where it is not valid",
                 detail: "serviceType belongs on Service only, not on "
                       + "LocalBusiness or FinancialService." });
      break;
    }
  }
  for (const n of nodes) {
    if (!n["@type"]) {
      out.push({ sev: "MINOR", id: "ld-no-type",
                 title: "A JSON-LD node has no @type" });
      break;
    }
  }

  // A FAQPage whose questions are not on the page is the one Google penalises.
  const text = String(pageText || "").toLowerCase().replace(/\s+/g, " ");
  if (text) {
    const qs = [];
    for (const n of nodes) {
      if (!TYPES_OF(n).includes("FAQPage")) continue;
      for (const q of [].concat(n.mainEntity || [])) {
        if (q && q.name) qs.push(String(q.name));
      }
    }
    const absent = qs.filter((q) => {
      const probe = q.toLowerCase().replace(/\s+/g, " ").slice(0, 40);
      return probe.length > 12 && !text.includes(probe);
    });
    if (absent.length) {
      out.push({ sev: "MAJOR", id: "ld-faq-invisible",
                 title: absent.length + " FAQ question(s) are in the schema but "
                      + "not in the visible text",
                 detail: JSON.stringify(absent[0]).slice(0, 90)
                       + " - the markup has to match what a visitor reads." });
    }
  }

  if (kind === "editorial" && !nodes.some((n) =>
      TYPES_OF(n).some((t) => t === "BlogPosting" || t === "Article" || t === "NewsArticle"))) {
    out.push({ sev: "MINOR", id: "ld-no-article",
               title: "An article page with no Article or BlogPosting block" });
  }
  return out;
}

/** The types a site is expected to carry somewhere, checked across the set. */
function judgeSchemaCoverage(allTypes, inners) {
  const out = [];
  const have = new Set(allTypes);
  if (!have.has("Organization") && !have.has("LocalBusiness")) {
    out.push({ sev: "MAJOR", id: "ld-no-org",
               title: "No Organization or LocalBusiness anywhere on the site" });
  }
  if (!have.has("WebSite")) {
    out.push({ sev: "MINOR", id: "ld-no-website",
               title: "No WebSite block, so no sitelinks search box is possible" });
  }
  if (inners > 0 && !have.has("BreadcrumbList")) {
    out.push({ sev: "MINOR", id: "ld-no-breadcrumb",
               title: "No BreadcrumbList on any page below the root",
               detail: inners + " inner page(s) checked." });
  }
  return out;
}

// ---------------------------------------------------------- content

const STOPWORDS = new Set(("the a an and or but of to in for on at by with from "
  + "is are was were be been being this that these those it its as we you your "
  + "our their his her they he she i us them not no yes do does did have has "
  + "had will would can could should may might must if then than so such about "
  + "all any more most other some out up down over under new get").split(" "));

// The verticals an injection almost always sells. On their own they prove
// nothing - a real pharmacy says "pharmacy" - so they are reported as a
// secondary signal and only alongside the structural evidence below.
const SPAM_VERTICAL = /\b(casino|slots?|betting|poker|viagra|cialis|tramadol|payday loan|escort|porn|replica watch|counterfeit|crypto giveaway|forex signals)\b/i;

/**
 * Thin pages, stuffed pages, and the fingerprint of an injection.
 *
 * The vertical word list is deliberately the weakest of the three signals.
 * What actually identifies a hacked page is structural: substantial text
 * hidden from a visitor but served to a crawler, or a sudden pile of links to
 * unrelated domains. Those happen for no legitimate reason, and they do not
 * depend on guessing which words are suspicious.
 */
function judgeContent(p) {
  const out = [];
  if (!p || !p.ok) return out;
  const text = String(p.bodyText || "");
  const words = text.toLowerCase().match(/[a-z][a-z'-]{1,}/g) || [];

  const utility = /\/(contact|thank|thanks|privacy|terms|cookie|404|search)/i
    .test(p.url);
  if (words.length && words.length < 300 && !utility && p.kind !== "hub") {
    out.push({ sev: "MINOR", id: "thin-content",
               title: "Thin page: " + words.length + " words",
               detail: "Under 300 words on a page that is meant to rank. The "
                     + "quality-focused updates act on exactly this." });
  }

  if (words.length >= 200) {
    const freq = {};
    for (const w of words) if (!STOPWORDS.has(w) && w.length > 3) freq[w] = (freq[w] || 0) + 1;
    const top = Object.entries(freq).sort((a, b) => b[1] - a[1])[0];
    if (top) {
      const share = top[1] / words.length;
      if (share > 0.06) {
        out.push({ sev: "MAJOR", id: "keyword-stuffing",
                   title: '"' + top[0] + '" is ' + (share * 100).toFixed(1)
                        + "% of the words on this page",
                   detail: top[1] + " of " + words.length + " words. Over about "
                         + "6% reads as stuffing rather than as writing." });
      } else if (share > 0.04) {
        out.push({ sev: "NOTE", id: "keyword-density",
                   title: '"' + top[0] + '" is ' + (share * 100).toFixed(1)
                        + "% of the words on this page",
                   detail: "Worth a look; not yet stuffing." });
      }
    }
  }

  // The structural fingerprint of an injection: hidden text that is not part
  // of any interface component and whose links leave the site. A collapsed
  // menu is hidden too, and links inward, which is why that is not enough on
  // its own.
  const h = p.hiddenText;
  if (h && h.words > 40 && (h.external >= 5 || SPAM_VERTICAL.test(h.sample))) {
    const vertical = SPAM_VERTICAL.test(h.sample);
    out.push({ sev: h.external >= 5 && vertical ? "BLOCKER" : "MAJOR",
               id: "hidden-text",
               title: h.words + " words hidden from visitors, linking off-site",
               detail: h.nodes + " hidden element(s) outside any menu or dialog, "
                     + "carrying " + h.external + " external link(s) and "
                     + h.internal + " internal."
                     + (vertical ? " The hidden text matches a known spam "
                                 + "vertical." : ""),
               fix: "Treat the site as compromised until proven otherwise: look "
                  + "for modified files and unknown admin users before deleting "
                  + "anything, and check whether the pages are indexed." });
  }
  if (p.offsiteLinks && p.offsiteLinks.count >= 20) {
    out.push({ sev: "MAJOR", id: "offsite-link-pile",
               title: p.offsiteLinks.count + " links to "
                    + p.offsiteLinks.hosts + " outside domains on one page",
               detail: "Sample: " + (p.offsiteLinks.sample || []).slice(0, 5).join(", ")
                     + ". Normal for a directory or a link roundup, and the "
                     + "usual shape of an injected link farm otherwise." });
  }
  if (SPAM_VERTICAL.test(text) && !SPAM_VERTICAL.test(String(p.title || ""))) {
    out.push({ sev: "NOTE", id: "spam-vertical-words",
               title: "Spam-vertical wording appears in the body but not the title",
               detail: "On its own this proves nothing - plenty of real sites use "
                     + "these words. Read the page before repeating it." });
  }
  return out;
}

// ------------------------------------------------------------------ NAP

/** Digits only, last 10 kept, so formatting differences stop mattering. */
function phoneKey(s) {
  const d = String(s || "").replace(/\D+/g, "");
  return d.length >= 7 ? d.slice(-10) : "";
}

/**
 * Does the site agree with itself about its own name, phone and address?
 *
 * The full audit needs the client's confirmed values, and those cannot be
 * inferred from the site because the site is the thing being audited. What
 * needs no source of truth at all is internal consistency: if three different
 * numbers appear across the pages, or the schema's telephone matches none of
 * the visible ones, that is a finding whichever one turns out to be right.
 */
function judgeNap(pages) {
  const out = [];
  const ok = pages.filter((p) => p.ok);
  if (!ok.length) return out;

  const visible = new Map();
  for (const p of ok) {
    for (const t of (p.telLinks || [])) {
      const k = phoneKey(t);
      if (k) {
        if (!visible.has(k)) visible.set(k, { shown: t, pages: new Set() });
        visible.get(k).pages.add(p.url);
      }
    }
  }
  if (visible.size > 1) {
    out.push({ sev: "MAJOR", id: "nap-phone-inconsistent",
               title: visible.size + " different phone numbers across the site",
               detail: Array.from(visible.values())
                 .map((v) => v.shown + " (" + v.pages.size + " page(s))")
                 .join(", ")
                     + ". A second number can be legitimate - a fax or a "
                     + "department line - so confirm with the client rather "
                     + "than picking one.",
               fix: "One number everywhere, or a documented reason for each." });
  }

  // The schema has to agree with what the page shows.
  const schemaPhones = new Set();
  const schemaNames = new Set();
  let addressNodes = 0;
  for (const p of ok) {
    for (const n of ldNodes(p.ldBlocks || [])) {
      const types = TYPES_OF(n);
      if (!types.some((t) => /LocalBusiness|Organization|.*Business|Dentist|Physician|Store/.test(t))) continue;
      if (n.telephone) schemaPhones.add(phoneKey(n.telephone));
      if (n.name) schemaNames.add(String(n.name).trim());
      if (n.address) addressNodes += 1;
    }
  }
  const sp = Array.from(schemaPhones).filter(Boolean);
  if (sp.length && visible.size && !sp.some((k) => visible.has(k))) {
    out.push({ sev: "MAJOR", id: "nap-schema-phone",
               title: "The schema's telephone matches no number shown on the site",
               detail: "Schema says " + sp.join(", ") + "; the pages show "
                     + Array.from(visible.keys()).join(", ")
                     + ". Schema that disagrees with the page is worse than no "
                     + "schema." });
  }
  if (schemaNames.size > 1) {
    out.push({ sev: "MINOR", id: "nap-schema-name",
               title: "The schema gives " + schemaNames.size + " different "
                    + "business names",
               detail: Array.from(schemaNames).slice(0, 4).join(" / ") });
  }
  if (sp.length && !addressNodes) {
    out.push({ sev: "MINOR", id: "nap-no-address",
               title: "Local schema has a phone number but no postal address" });
  }
  return out;
}

// ------------------------------------------------------ internal linking

const EDITORIAL_HEADS = new Set(["blog", "news", "article", "articles", "learn",
  "resource", "resources", "insight", "insights", "guide", "guides", "post",
  "posts", "kb", "help", "docs", "press", "updates", "stories"]);
const STATIC_HEADS = new Set(["service", "services", "about", "about-us",
  "contact", "contact-us", "team", "staff", "doctors", "pricing", "insurance",
  "billing", "privacy", "privacy-policy", "terms", "terms-and-conditions",
  "legal", "category", "tag", "author"]);

/**
 * What kind of page this is, from its address.
 *
 * It decides where a new internal link may be *placed*: editorial content only.
 * A hub like `/blog/` is an archive, not an article, so it is not a source
 * either - which is why the editorial heads need a segment after them.
 */
function pageKind(u) {
  let p;
  try { p = new URL(u).pathname.replace(/\/+$/, ""); } catch { return "other"; }
  if (!p || p === "") return "static";
  const segs = p.split("/").filter(Boolean);
  const head = (segs[0] || "").toLowerCase();
  if (/^\d{4}$/.test(head) && segs.length >= 2) return "editorial";
  if (EDITORIAL_HEADS.has(head)) return segs.length > 1 ? "editorial" : "hub";
  if (STATIC_HEADS.has(head)) return "static";
  return "other";
}

function siloOf(u) {
  try {
    const segs = new URL(u).pathname.split("/").filter(Boolean);
    return segs.length ? segs[0].toLowerCase() : "(root)";
  } catch { return "(root)"; }
}

const VAGUE_ANCHOR = /^(click here|read more|learn more|more|here|this|link|continue reading|see more|find out more|details)$/i;

/** Who links to whom, from the pages that were actually read. */
function buildGraph(pages) {
  const norm = (u) => { try { const x = new URL(u); return x.origin + x.pathname.replace(/\/+$/, "") || x.origin; } catch { return null; } };
  const nodes = new Map();
  const touch = (u) => {
    const k = norm(u);
    if (!k) return null;
    if (!nodes.has(k)) nodes.set(k, { url: k, inbound: 0, inContent: 0, outContent: 0, anchors: [] });
    return nodes.get(k);
  };
  for (const p of pages) if (p.ok) touch(p.url);
  for (const p of pages) {
    if (!p.ok) continue;
    const from = norm(p.url);
    for (const a of (p.anchors || [])) {
      const to = norm(a.href);
      if (!to || to === from) continue;
      const n = touch(to);
      if (!n) continue;
      n.inbound += 1;
      if (!a.nav) {
        n.inContent += 1;
        n.anchors.push({ text: (a.text || "").trim(), from });
        const f = touch(p.url);
        if (f) f.outContent += 1;
      }
    }
  }
  return nodes;
}

/**
 * The link structure, judged only as far as the crawl can support.
 *
 * An orphan claim is a claim about the whole site, so it cannot be made from a
 * partial crawl: a page linked only from the 180 pages that were not read
 * would be reported as orphaned. Below full coverage the count is withheld and
 * the report says why, which is the honest version of a number that would
 * otherwise look authoritative.
 */
function judgeInternalLinking(nodes, pages, coverage) {
  const out = [];
  const list = Array.from(nodes.values()).filter((n) =>
    pages.some((p) => p.ok && n.url === String(p.url).replace(/\/+$/, "")));

  const orphans = list.filter((n) => n.inbound === 0);
  if (coverage !== null && coverage >= 0.9) {
    if (orphans.length) {
      out.push({ sev: "MAJOR", id: "orphans",
                 title: orphans.length + " page(s) have no internal link pointing at them",
                 detail: orphans.slice(0, 6).map((n) => n.url).join(", ")
                       + " - reachable only from the sitemap." });
    }
  } else if (orphans.length) {
    out.push({ sev: "NOTE", id: "orphans-unknown",
               title: "Orphan pages were not counted",
               detail: coverage === null
                 ? "There is no readable sitemap to compare against, so the "
                 + "full page list is unknown and nothing can be called an "
                 + "orphan. Fix the sitemap first."
                 : "Only " + Math.round(coverage * 100) + "% of the sitemap "
                 + "was read, and a page linked from an unread page would "
                 + "look orphaned. Raise --pages to count them." });
  }

  const thin = list.filter((n) => pageKind(n.url) === "editorial" && n.outContent < 3);
  if (thin.length) {
    out.push({ sev: "MINOR", id: "thin-internal-links",
               title: thin.length + " article(s) carry fewer than 3 in-content internal links",
               detail: thin.slice(0, 5).map((n) => n.url + " (" + n.outContent + ")")
                 .join(", ") });
  }

  // Anchor quality is a property of the page the link sits ON, and every
  // anchor here was collected from a page that was read. Restricting these to
  // destinations that were also read dropped every link pointing at a page
  // outside the crawl - which is most of them.
  const all = Array.from(nodes.values());
  const byText = {};
  for (const n of all) {
    for (const a of n.anchors) {
      if (!a.text) continue;
      const k = a.text.toLowerCase();
      (byText[k] = byText[k] || new Set()).add(a.from);
    }
  }
  const repeated = Object.entries(byText).filter(([, srcs]) => srcs.size >= 5);
  if (repeated.length) {
    out.push({ sev: "MINOR", id: "anchor-repetition",
               title: repeated.length + " anchor text(s) repeat across 5 or more pages",
               detail: repeated.slice(0, 3)
                 .map(([t, s]) => JSON.stringify(t.slice(0, 32)) + " x" + s.size).join(", ")
                     + " - vary it; the same exact-match anchor sitewide reads as a pattern." });
  }

  const vague = [];
  for (const n of all) {
    for (const a of n.anchors) if (VAGUE_ANCHOR.test(a.text || "")) vague.push(a.text);
  }
  if (vague.length) {
    out.push({ sev: "MINOR", id: "anchor-vague",
               title: vague.length + " internal link(s) use non-descriptive anchor text",
               detail: Array.from(new Set(vague)).slice(0, 5).join(", ")
                     + " - the anchor should say where it goes." });
  }
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
  res.ldBlocks = parseLd(raw);
  res.ldTypes = ldNodes(res.ldBlocks).flatMap(TYPES_OF);
  res.kind = pageKind(url);
  res.silo = siloOf(url);
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
      // Anchor text as well, for the linking checks, and the visible text so
      // a FAQ block can be compared against what a visitor actually reads.
      anchors: Array.from(document.querySelectorAll("a[href]")).map((a) => ({
        href: a.href,
        text: (a.textContent || "").replace(/\s+/g, " ").trim().slice(0, 80),
        nav: !!a.closest("nav,header,footer,aside"),
      })),
      telLinks: Array.from(document.querySelectorAll('a[href^="tel:"]'))
        .map((a) => a.getAttribute("href").replace(/^tel:/i, "").trim()),
      bodyText: ((document.body && document.body.innerText) || "")
        .replace(/\s+/g, " ").slice(0, 20000),
      // Text served to a crawler and hidden from a visitor - but only the kind
      // that has no innocent explanation.
      //
      // Hidden text on its own is everywhere: collapsed menus, dropdowns,
      // accordions, tab panels, modals and skip links are all display:none
      // until used. Measured on a documentation site, a first version of this
      // reported 191 hidden words across 6 elements carrying 43 links as a
      // blocker, and every one of them was a collapsed navigation panel.
      //
      // So anything that belongs to a recognisable interface component is
      // skipped, and what is left is reported only when its links point off
      // this site - which is what an injected block is for and what a menu
      // never does.
      hiddenText: (() => {
        const here = location.hostname.replace(/^www\./, "");
        const UI = "nav,header,footer,details,dialog,[hidden],[aria-expanded],"
          + "[aria-hidden],[role=menu],[role=menubar],[role=menuitem],"
          + "[role=tablist],[role=tabpanel],[role=dialog],[role=navigation],"
          + "[role=tooltip],[popover]";
        const UI_CLASS = /menu|nav|dropdown|accordion|collapse|modal|dialog|tab|drawer|offcanvas|popover|tooltip|carousel|slider|skip|sr-only|visually-hidden|screen-reader/i;
        let words = 0, nodes = 0, ext = 0, int = 0, sample = "";
        for (const el of Array.from(document.querySelectorAll("div,span,p,section,ul,li"))) {
          const cs = getComputedStyle(el);
          const off = parseInt(cs.textIndent || "0", 10) <= -1000
            || parseInt(cs.left || "0", 10) <= -1000;
          if (!(cs.display === "none" || cs.visibility === "hidden" || off)) continue;
          if (el.closest(UI)) continue;
          if (UI_CLASS.test(el.className || "") ) continue;
          if (el.parentElement && el.parentElement.closest("[data-hidden-counted]")) continue;
          el.setAttribute("data-hidden-counted", "1");
          const t = (el.textContent || "").replace(/\s+/g, " ").trim();
          const n = (t.match(/\S+/g) || []).length;
          if (n < 5) continue;
          let e = 0, i = 0;
          for (const a of Array.from(el.querySelectorAll("a[href]"))) {
            let h;
            try { h = new URL(a.href).hostname.replace(/^www\./, ""); } catch { continue; }
            if (h && h !== here) e += 1; else i += 1;
          }
          words += n; nodes += 1; ext += e; int += i;
          if (sample.length < 300) sample += " " + t.slice(0, 200);
        }
        return { words, nodes, links: ext + int, external: ext, internal: int,
                 sample: sample.trim() };
      })(),
      offsiteLinks: (() => {
        const here = location.hostname.replace(/^www\./, "");
        const hosts = {};
        let count = 0;
        for (const a of Array.from(document.querySelectorAll("a[href]"))) {
          let h;
          try { h = new URL(a.href).hostname.replace(/^www\./, ""); } catch { continue; }
          if (!h || h === here) continue;
          count += 1;
          hosts[h] = (hosts[h] || 0) + 1;
        }
        return { count, hosts: Object.keys(hosts).length,
                 sample: Object.keys(hosts).slice(0, 8) };
      })(),
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
  findings.push(...judgeNap(pages));

  // Structured data and content quality, per page.
  for (const p of pages) {
    if (!p.ok) continue;
    for (const f of judgeSchema(p.ldBlocks || [], p.bodyText, p.kind)) {
      findings.push(Object.assign({ where: p.url }, f));
    }
    for (const f of judgeContent(p)) {
      findings.push(Object.assign({ where: p.url }, f));
    }
  }
  const allTypes = pages.filter((p) => p.ok).flatMap((p) => p.ldTypes || []);
  const inners = pages.filter((p) => p.ok && pageKind(p.url) !== "static"
    && new URL(p.url).pathname.replace(/\/+$/, "") !== "").length;
  findings.push(...judgeSchemaCoverage(allTypes, inners));

  // The link structure, as far as the crawl can support a claim about it.
  const graph = buildGraph(pages);
  // null, not 1. With no sitemap there is nothing to measure coverage against,
  // and defaulting to "complete" let the orphan count be claimed on a site
  // whose sitemap had not been read at all - measured on a live site, which
  // reported both "the sitemap lists no URLs" and "coverage 100%".
  const coverage = sm.count ? pages.filter((p) => p.ok).length / sm.count : null;
  findings.push(...judgeInternalLinking(graph, pages, coverage));

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
    "schema types found": Array.from(new Set(allTypes)).sort().join(", ") || MISSING,
    "pages with invalid JSON-LD":
      ok.filter((p) => (p.ldBlocks || []).some((b) => !b.ok)).length,
    // Only pages that were actually read. Counting graph nodes counted
    // every page merely discovered through a link, which has zero
    // outgoing links because it was never opened - 26 of them on a site
    // where 6 pages had been read.
    "articles with fewer than 3 in-content links":
      Array.from(graph.values()).filter((n) =>
        pageKind(n.url) === "editorial" && n.outContent < 3
        && ok.some((p) => String(p.url).replace(/\/+$/, "") === n.url)).length,
    "sitemap coverage read":
      coverage === null ? "no sitemap to compare against"
                        : Math.round(coverage * 100) + "%",
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
                   parseLd, ldNodes, judgeSchema, judgeSchemaCoverage, judgeContent,
                   pageKind, siloOf, buildGraph, judgeInternalLinking,
                   judgeNap, phoneKey, opensAlike, wordsOf,
                   judgeCanonical, judgeRobots, judge404, judgeLinks,
                   judgeSitemap, judgePage, classifyLink, entityLeak, similar,
                   firstWords, sortFindings, report, LIMITS, AI_AGENTS, MISSING };
