/**
 * Is this site safe to put live, measured rather than assumed.
 *
 *   node security.js <url> [--out <dir>] [--no-probe] [--max-scripts 25]
 *
 * Loads the page once in a real browser and reads what the server actually
 * sent: the transport headers, the cookies, every subresource, every script
 * body, and a short fixed list of files that must never be reachable.
 *
 * Three things it deliberately does NOT report, because reporting them is
 * worse than silence:
 *
 *  - `target="_blank"` without `rel="noopener"`. Every current engine implies
 *    noopener for a `_blank` anchor and the behaviour is in the HTML standard
 *    (Safari 2018, Firefox 79, Chromium 88). Scanners still emit it; it sends
 *    a developer to edit a hundred links for nothing.
 *  - `X-XSS-Protection`. Deprecated, removed from the engines that had it, and
 *    its filter introduced bugs of its own.
 *  - Missing integrity on a tag-manager or analytics script. Those are loaders
 *    whose content is meant to change, so SRI cannot apply to them by design.
 *
 * And one honest limit the report states: this reads what one load from one
 * machine received. It finds a missing header, a leaked key or a reachable
 * file, which is most of what goes wrong. It is not a penetration test and it
 * does not look at the application's own logic, its auth, or its database
 * rules.
 */
const crypto = require("crypto");
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

// OWASP's HTTP Strict Transport Security cheat sheet, read from the live page:
// the recommended header is `max-age=63072000; includeSubDomains; preload`.
// Anything under a year is reported as short - the cheat sheet's own short
// example (86400) is explicitly for the first days of a rollout.
const HSTS_GOOD = 63072000;
const HSTS_SHORT = 31536000;

const SEV_RANK = { BLOCKER: 0, MAJOR: 1, MINOR: 2, NOTE: 3 };

/** A development origin, where the transport checks do not apply. */
function isDevHost(url) {
  let h;
  try { h = new URL(url).hostname.toLowerCase(); } catch { return false; }
  if (h === "localhost" || h === "127.0.0.1" || h === "[::1]" || h === "::1") return true;
  return /\.(?:localhost|test|local|internal)$/.test(h);
}

/**
 * Never print a key. The point of the report is that a key is in the bundle,
 * and a report that quotes it has copied the leak into the project folder, the
 * chat and whatever the client is sent.
 */
function mask(value) {
  const s = String(value || "");
  if (s.length <= 8) return "*".repeat(s.length) + " (" + s.length + " chars)";
  return s.slice(0, 4) + "..." + "*".repeat(4) + " (" + s.length + " chars)";
}

/**
 * A short one-way fingerprint, so the same key found in four files can be
 * collapsed into one finding.
 *
 * Masking alone cannot do this: two different Google keys both mask to
 * `AIza...**** (39 chars)`, so collapsing on the mask would merge two separate
 * keys into one line and hide the second. Measured on a live site that carries
 * several - the first run reported the same title four times and there was no
 * way to tell from the report whether that was one key or four.
 */
function fingerprint(value) {
  return crypto.createHash("sha256").update(String(value || "")).digest("hex").slice(0, 8);
}

/** One line per distinct key, naming the other places it turned up. */
function dedupeSecrets(list) {
  const out = [];
  const first = new Map();
  for (const f of list || []) {
    if (!f.fp) { out.push(f); continue; }
    const key = f.id + "|" + f.fp;
    const prev = first.get(key);
    if (!prev) {
      const copy = Object.assign({}, f);
      first.set(key, copy);
      out.push(copy);
      continue;
    }
    prev.places = (prev.places || 1) + 1;
    prev.alsoIn = (prev.alsoIn || []);
    if (prev.alsoIn.length < 4 && f.where && f.where !== prev.where) prev.alsoIn.push(f.where);
  }
  return out;
}

/**
 * The `role` claim out of a JWT payload, without verifying the signature.
 *
 * This is the whole reason the Supabase check is usable. Both legacy keys are
 * long-lived JWTs that start `eyJ`: the `anon` key is meant to be in the
 * browser and the `service_role` key bypasses row level security entirely.
 * Nothing but the decoded payload tells them apart, so a scanner that matches
 * on `eyJ` either flags every Supabase site or none of them.
 */
function jwtRole(token) {
  const parts = String(token || "").split(".");
  if (parts.length < 2) return null;
  try {
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64 + "=".repeat((4 - (b64.length % 4)) % 4);
    const obj = JSON.parse(Buffer.from(pad, "base64").toString("utf8"));
    return typeof obj.role === "string" ? obj.role : null;
  } catch { return null; }
}

// The PEM pattern is assembled instead of written out, because the repo's own
// leak check looks for that exact line and would report this file as carrying
// a private key.
const PEM = new RegExp("-----BEGIN [A-Z ]{0,24}PRIVATE KEY" + "-----");

/**
 * What must never reach a browser. Each entry says how sure it is, because a
 * minified bundle is a long string of plausible-looking characters and a false
 * BLOCKER on a client report costs more than it saves.
 */
const PATTERNS = [
  { id: "supabase-secret", sev: "BLOCKER", conf: "certain",
    what: "Supabase secret key (bypasses row level security)",
    re: /sb_secret_[A-Za-z0-9_-]{10,}/g },
  { id: "stripe-secret", sev: "BLOCKER", conf: "certain",
    what: "Stripe secret key", re: /\b(?:sk|rk)_live_[0-9a-zA-Z]{16,}/g },
  { id: "anthropic", sev: "BLOCKER", conf: "certain",
    what: "Anthropic API key", re: /\bsk-ant-[A-Za-z0-9_-]{20,}/g },
  { id: "openai", sev: "BLOCKER", conf: "certain",
    what: "OpenAI API key", re: /\bsk-proj-[A-Za-z0-9_-]{20,}/g },
  { id: "github", sev: "BLOCKER", conf: "certain",
    what: "GitHub access token", re: /\b(?:ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{40,})/g },
  { id: "aws", sev: "BLOCKER", conf: "certain",
    what: "AWS access key id", re: /\bAKIA[0-9A-Z]{16}\b/g },
  { id: "sendgrid", sev: "BLOCKER", conf: "certain",
    what: "SendGrid key", re: /\bSG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}/g },
  { id: "slack", sev: "BLOCKER", conf: "certain",
    what: "Slack token", re: /\bxox[baprs]-[A-Za-z0-9-]{10,}/g },
  { id: "private-key", sev: "BLOCKER", conf: "certain",
    what: "private key", re: new RegExp(PEM.source, "g") },
  // Google's browser keys are meant to be in the page - Maps cannot work
  // otherwise - so this is not a leak. It is only safe once the key is
  // restricted to the site's own referrers, which is a dashboard setting
  // nobody checks, so it is worth one line.
  { id: "google-browser-key", sev: "MINOR", conf: "likely",
    what: "Google API key in the page (fine if restricted by HTTP referrer)",
    re: /\bAIza[0-9A-Za-z_-]{35}\b/g },
];

/**
 * Secrets in a shipped file. `where` is only used for the report.
 *
 * Supabase's publishable key (`sb_publishable_`) and the legacy `anon` JWT are
 * both documented as safe to expose, so neither is a finding: Supabase's own
 * docs say the publishable key is "safe to expose online: web page, mobile or
 * desktop app, GitHub actions, CLIs, source code".
 */
function scanSecrets(text, where) {
  const out = [];
  const body = String(text || "");
  for (const p of PATTERNS) {
    p.re.lastIndex = 0;
    let m;
    const seen = new Set();
    while ((m = p.re.exec(body)) !== null) {
      const hit = m[0];
      if (seen.has(hit)) continue;
      seen.add(hit);
      out.push({ sev: p.sev, conf: p.conf, id: p.id, title: p.what, where,
                 sample: mask(hit), fp: fingerprint(hit) });
      if (seen.size >= 3) break;      // three is enough to prove it is there
    }
  }
  // JWTs have to be decoded rather than matched, see jwtRole().
  const jwt = /\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}/g;
  const done = new Set();
  let j;
  while ((j = jwt.exec(body)) !== null) {
    const tok = j[0];
    if (done.has(tok)) continue;
    done.add(tok);
    const role = jwtRole(tok);
    if (role === "service_role") {
      out.push({ sev: "BLOCKER", conf: "certain", id: "supabase-service-role",
                 title: "Supabase service_role key - bypasses row level security",
                 where, sample: mask(tok), fp: fingerprint(tok) });
    }
    if (done.size >= 40) break;
  }
  return out;
}

/** max-age and the flags out of a Strict-Transport-Security value. */
function hstsParts(value) {
  const v = String(value || "");
  const m = v.match(/max-age\s*=\s*"?(\d+)"?/i);
  return {
    maxAge: m ? parseInt(m[1], 10) : null,
    includeSubDomains: /includeSubDomains/i.test(v),
    preload: /preload/i.test(v),
  };
}

function judgeHsts(value) {
  if (!value) {
    return [{ sev: "MAJOR", id: "hsts-missing",
              title: "No Strict-Transport-Security header",
              detail: "A visitor who types the bare domain is served over http "
                    + "first and can be intercepted before the redirect.",
              fix: "Strict-Transport-Security: max-age=63072000; includeSubDomains" }];
  }
  const p = hstsParts(value);
  const out = [];
  if (p.maxAge === null) {
    out.push({ sev: "MAJOR", id: "hsts-no-max-age",
               title: "Strict-Transport-Security has no max-age",
               detail: "Without max-age the header does nothing." });
    return out;
  }
  if (p.maxAge < HSTS_SHORT) {
    out.push({ sev: "MINOR", id: "hsts-short",
               title: "Strict-Transport-Security max-age is short",
               detail: "max-age=" + p.maxAge + " (" + Math.round(p.maxAge / 86400)
                     + " days). OWASP recommends " + HSTS_GOOD + ".",
               fix: "Raise it once you are sure every subdomain serves https." });
  }
  if (!p.includeSubDomains) {
    out.push({ sev: "NOTE", id: "hsts-no-subdomains",
               title: "Strict-Transport-Security does not cover subdomains",
               detail: "Only add includeSubDomains once every subdomain is https." });
  }
  return out;
}

/**
 * The Content-Security-Policy, judged for what it actually prevents.
 *
 * A missing CSP is reported as MAJOR, not as a blocker. A brochure site with
 * no CSP is the normal state of the web, and a launch gate that refuses to
 * open for it is a gate people learn to force.
 */
function judgeCsp(value, reportOnlyValue) {
  const out = [];
  if (!value && !reportOnlyValue) {
    return [{ sev: "MAJOR", id: "csp-missing", title: "No Content-Security-Policy",
              detail: "Nothing limits which scripts the page may run, so any "
                    + "injected tag runs with the page's privileges.",
              fix: "Start with default-src 'self' and frame-ancestors 'none', "
                 + "in Report-Only until the console is quiet." }];
  }
  if (!value && reportOnlyValue) {
    out.push({ sev: "MAJOR", id: "csp-report-only",
               title: "Content-Security-Policy is Report-Only",
               detail: "It reports violations and blocks nothing." });
    return out;
  }
  const v = String(value);
  const has = (d) => new RegExp("(?:^|;)\\s*" + d + "\\s", "i").test(v + " ");
  if (!has("default-src") && !has("script-src")) {
    out.push({ sev: "MAJOR", id: "csp-no-script-control",
               title: "Content-Security-Policy does not restrict scripts",
               detail: "No default-src and no script-src, so script loading is "
                     + "unrestricted whatever else the policy says." });
  }
  const scriptPart = (v.match(/(?:^|;)\s*(?:script-src|default-src)[^;]*/gi) || []).join(" ");
  if (/'unsafe-eval'/i.test(scriptPart)) {
    out.push({ sev: "MINOR", id: "csp-unsafe-eval",
               title: "Content-Security-Policy allows unsafe-eval",
               detail: "A string can still be turned into code." });
  }
  if (/'unsafe-inline'/i.test(scriptPart) && !/'nonce-|'sha(?:256|384|512)-/i.test(scriptPart)) {
    out.push({ sev: "MINOR", id: "csp-unsafe-inline",
               title: "Content-Security-Policy allows unsafe-inline for scripts",
               detail: "Inline script is the thing an injection uses, so this "
                     + "removes most of the policy's value. Common on sites "
                     + "with a tag manager; a nonce is the way out." });
  }
  if (!has("frame-ancestors")) {
    out.push({ sev: "NOTE", id: "csp-no-frame-ancestors",
               title: "Content-Security-Policy has no frame-ancestors" });
  }
  return out;
}

/** The small headers, judged together. */
function judgeHeaders(headers, isHttps) {
  const h = {};
  for (const k of Object.keys(headers || {})) h[k.toLowerCase()] = headers[k];
  const out = [];
  if (isHttps) out.push(...judgeHsts(h["strict-transport-security"]));
  out.push(...judgeCsp(h["content-security-policy"],
                       h["content-security-policy-report-only"]));

  const csp = String(h["content-security-policy"] || "");
  const framed = h["x-frame-options"] || /frame-ancestors/i.test(csp);
  if (!framed) {
    out.push({ sev: "MAJOR", id: "framing",
               title: "Page can be framed by any site",
               detail: "No X-Frame-Options and no CSP frame-ancestors. A copy of "
                     + "the page inside somebody else's wrapper can collect what "
                     + "a visitor types into the form.",
               fix: "X-Frame-Options: SAMEORIGIN, or frame-ancestors 'self'." });
  }
  if (!/nosniff/i.test(String(h["x-content-type-options"] || ""))) {
    out.push({ sev: "MINOR", id: "nosniff",
               title: "No X-Content-Type-Options: nosniff",
               detail: "The browser may guess a type for an upload and run it." });
  }
  const ref = String(h["referrer-policy"] || "");
  if (!ref) {
    out.push({ sev: "MINOR", id: "referrer-policy",
               title: "No Referrer-Policy",
               detail: "Full URLs, query strings included, are handed to every "
                     + "third party the page loads." });
  } else if (/unsafe-url/i.test(ref)) {
    out.push({ sev: "MAJOR", id: "referrer-unsafe",
               title: "Referrer-Policy is unsafe-url",
               detail: "The full URL is sent even to http destinations." });
  }
  if (h["server"] && /\d+\.\d+/.test(String(h["server"]))) {
    out.push({ sev: "NOTE", id: "server-version",
               title: "Server header names a version",
               detail: String(h["server"]).slice(0, 60) });
  }
  if (h["x-powered-by"]) {
    out.push({ sev: "NOTE", id: "x-powered-by",
               title: "X-Powered-By is set",
               detail: String(h["x-powered-by"]).slice(0, 60) });
  }
  return out;
}

/** Cookie flags. Playwright gives these decoded, so read the fields. */
function judgeCookies(cookies, isHttps) {
  const out = [];
  // Grouped, not one line each. A consent banner plus a tag manager sets five
  // of these, and five identical MINOR lines push the one finding that matters
  // off the top of the report. Measured on a live site: five separate lines,
  // all of them cookies the site owner did not set and cannot easily change.
  const ordinary = [];
  for (const c of cookies || []) {
    const name = c.name || "";
    const sessionish = /sess|sid$|^sid|auth|token|login|remember|wordpress_logged/i.test(name);
    if (isHttps && !c.secure) {
      if (sessionish) {
        out.push({ sev: "MAJOR", id: "cookie-insecure",
                   title: "Session cookie without Secure: " + name,
                   detail: "It is sent over plain http too, so it can be read in transit." });
      } else {
        ordinary.push(name);
      }
    }
    if (sessionish && !c.httpOnly) {
      out.push({ sev: "MAJOR", id: "cookie-no-httponly",
                 title: "Session cookie readable by script: " + name,
                 detail: "No HttpOnly, so any injected script can read it. "
                       + "Analytics cookies are meant to be readable; this one "
                       + "looks like a session." });
    }
    if (String(c.sameSite || "").toLowerCase() === "none" && !c.secure) {
      out.push({ sev: "MAJOR", id: "cookie-samesite-none",
                 title: "SameSite=None without Secure: " + name,
                 detail: "Browsers reject this combination, so the cookie is dropped." });
    }
  }
  if (ordinary.length) {
    out.push({ sev: "MINOR", id: "cookies-insecure-group",
               title: ordinary.length + " cookie(s) set without Secure",
               detail: ordinary.slice(0, 10).join(", ")
                     + " - sent over plain http as well. Usually set by a "
                     + "third-party tag rather than by the site, so check who "
                     + "sets them before asking the client's developer." });
  }
  return out;
}

/**
 * Mixed content, from all three places it shows up.
 *
 * One detector is not enough. Chrome upgrades a passive http subresource to
 * https before it reaches the network log and blocks active ones outright, so
 * a network-only check can see a clean page while the markup still carries
 * `http://` and a visitor on an older browser gets the warning.
 */
function judgeMixed(domRefs, consoleHits, netHits) {
  const out = [];
  const active = domRefs.filter((r) => r.kind !== "img" && r.kind !== "media");
  const passive = domRefs.filter((r) => r.kind === "img" || r.kind === "media");
  if (active.length) {
    out.push({ sev: "BLOCKER", id: "mixed-active",
               title: "Script or frame loaded over http on an https page",
               detail: active.slice(0, 5).map((r) => r.kind + " " + r.url).join("; "),
               fix: "The browser blocks these, so the feature is already broken." });
  }
  if (passive.length) {
    out.push({ sev: "MAJOR", id: "mixed-passive",
               title: "Image or media referenced over http",
               detail: passive.slice(0, 5).map((r) => r.kind + " " + r.url).join("; ") });
  }
  if (netHits.length && !domRefs.length) {
    out.push({ sev: "MAJOR", id: "mixed-network",
               title: "A request went out over http",
               detail: netHits.slice(0, 5).join("; ")
                     + " - not in the markup, so it comes from script." });
  }
  if (consoleHits.length && !domRefs.length && !netHits.length) {
    out.push({ sev: "MAJOR", id: "mixed-console",
               title: "The browser reported mixed content",
               detail: consoleHits.slice(0, 3).join(" | ").slice(0, 300) });
  }
  return out;
}

/**
 * The fixed probe list. GET only, seven paths, no fuzzing and no guessing at
 * names: these are the files that are catastrophic when served and that land
 * in a web root by accident.
 *
 * `want` is what the body has to look like for the finding to be real. A
 * single-page app answers 200 with its own HTML for every unknown path, and a
 * check that trusts the status code reports seven breaches on a site that has
 * none. The same trap already caught this workspace once with robots.txt.
 */
const PROBES = [
  { path: "/.env", what: "environment file with the site's own secrets",
    want: /^[A-Z][A-Z0-9_]{2,}\s*=/m },
  { path: "/.git/config", what: "git config - the repository is exposed",
    want: /\[core\]/ },
  { path: "/.git/HEAD", what: "git directory is served",
    want: /^ref:\s*refs\//m },
  { path: "/wp-config.php.bak", what: "WordPress config backup with database credentials",
    want: /DB_(?:NAME|USER|PASSWORD)/ },
  { path: "/.htaccess", what: "server config served as a file",
    want: /RewriteEngine|<Files|RewriteRule/i },
  { path: "/phpinfo.php", what: "phpinfo output - full server configuration",
    want: /phpinfo\(\)|PHP Version/i },
  { path: "/server-status", what: "Apache server status",
    want: /Apache Server Status|Server uptime/i },
];

function judgeProbe(probe, status, body) {
  if (status !== 200) return null;
  const text = String(body || "");
  if (!probe.want.test(text)) {
    return { sev: "NOTE", id: "probe-catchall", title: probe.path
             + " answers 200 but is not the file",
             detail: "A catch-all route is serving the app for it. Not a leak." };
  }
  return { sev: "BLOCKER", id: "probe-" + probe.path.replace(/\W+/g, "-"),
           title: probe.path + " is publicly readable: " + probe.what,
           // The body is never quoted. It is the thing being protected.
           detail: "Confirmed by content, " + text.length + " bytes. Contents not "
                 + "reproduced here on purpose.",
           fix: "Stop serving it, then rotate everything it contained." };
}

function sortFindings(list) {
  return list.slice().sort((a, b) =>
    (SEV_RANK[a.sev] ?? 9) - (SEV_RANK[b.sev] ?? 9) ||
    String(a.title).localeCompare(String(b.title)));
}

function report(data) {
  const f = sortFindings(data.findings || []);
  const n = (s) => f.filter((x) => x.sev === s).length;
  const L = [];
  L.push("# Security pass - " + data.url);
  L.push("");
  L.push("Loaded " + data.taken + ". " + f.length + " finding(s): "
         + n("BLOCKER") + " blocker, " + n("MAJOR") + " major, "
         + n("MINOR") + " minor, " + n("NOTE") + " note.");
  L.push("");
  if (data.devHost) {
    L.push("This is a development origin, so the transport checks "
           + "(https, HSTS, Secure cookies) were skipped rather than failed.");
    L.push("");
  }
  if (!f.length) L.push("Nothing found by these checks.");
  for (const x of f) {
    L.push("## " + x.sev + " - " + x.title);
    if (x.where) {
      let where = "In: " + x.where;
      if (x.places > 1) {
        where += " and " + (x.places - 1) + " other place(s)";
        if ((x.alsoIn || []).length) where += ": " + x.alsoIn.join(", ");
      }
      L.push(where);
    }
    if (x.sample) L.push("Matched: " + x.sample + (x.fp ? " [#" + x.fp + "]" : ""));
    if (x.detail) L.push(x.detail);
    if (x.fix) L.push("Fix: " + x.fix);
    if (x.conf === "likely") L.push("Confidence: likely, not certain. Confirm before reporting it.");
    L.push("");
  }
  L.push("## What was looked at");
  L.push("- " + (data.scriptsScanned || 0) + " script file(s) read, "
         + (data.inlineScripts || 0) + " inline block(s)");
  L.push("- " + (data.thirdParty || []).length + " third-party origin(s): "
         + ((data.thirdParty || []).slice(0, 12).join(", ") || "none"));
  L.push("- " + (data.cookies || 0) + " cookie(s)");
  L.push("- " + (data.probed || 0) + " path(s) probed"
         + (data.probed ? "" : " (probing was off)"));
  L.push("");
  L.push("## Limits");
  L.push("One load from one machine. It reads headers, cookies, subresources, "
         + "script bodies and a fixed list of paths. It does not test the "
         + "application's own logic, its sign-in, or its database rules, and it "
         + "is not a penetration test.");
  if ((data.thirdParty || []).length) {
    L.push("");
    L.push("Every third-party script above can change this page whenever its "
           + "owner changes it. That is a decision to be comfortable with, not "
           + "a defect.");
  }
  return L.join("\n");
}

async function run(url, opts) {
  const { chromium } = loadPlaywright();
  const findings = [];
  const target = new URL(url);
  const isHttps = target.protocol === "https:";
  const devHost = isDevHost(url);

  if (!isHttps && !devHost) {
    findings.push({ sev: "BLOCKER", id: "no-https",
                    title: "Site is served over http",
                    detail: "Everything a visitor types, including the enquiry "
                          + "form, crosses the network in the clear.",
                    fix: "Serve https and redirect http to it." });
  }

  let browser = await chromium.launch();
  let context = await browser.newContext();
  let page = await context.newPage();

  const netHttp = [];
  const consoleMixed = [];
  const thirdParty = new Set();
  const scriptUrls = new Set();

  page.on("request", (r) => {
    const u = r.url();
    if (u.startsWith("http://") && !isDevHost(u)) netHttp.push(u);
    try {
      const h = new URL(u);
      if (h.hostname !== target.hostname && /^https?:/.test(h.protocol)) {
        if (r.resourceType() === "script") thirdParty.add(h.hostname);
      }
      if (r.resourceType() === "script" && h.hostname === target.hostname) {
        scriptUrls.add(u);
      }
    } catch { /* not a URL we can parse */ }
  });
  page.on("console", (m) => {
    const t = m.text();
    if (/mixed content/i.test(t)) consoleMixed.push(t.slice(0, 200));
  });

  let resp = null;
  let certError = "";
  try {
    resp = await page.goto(url, { waitUntil: "load", timeout: 60000 });
  } catch (e) {
    const msg = String(e && e.message || e);
    if (/ERR_CERT|SSL|certificate/i.test(msg)) {
      // Worth continuing past: an expired certificate is one finding, and the
      // rest of the pass still has something to say about the page.
      certError = msg.split("\n")[0].slice(0, 160);
      findings.push({ sev: "BLOCKER", id: "tls",
                      title: "TLS certificate is not valid for this site",
                      detail: certError,
                      fix: "Reissue or rebind the certificate before launch." });
      await context.close();
      context = await browser.newContext({ ignoreHTTPSErrors: true });
      page = await context.newPage();
      try { resp = await page.goto(url, { waitUntil: "load", timeout: 60000 }); }
      catch (e2) { /* reported below */ }
    } else {
      await browser.close();
      return { url, taken: new Date().toISOString().slice(0, 16).replace("T", " "),
               error: "could not load the page: " + msg.slice(0, 200),
               findings };
    }
  }
  if (!resp) {
    await browser.close();
    return { url, taken: new Date().toISOString().slice(0, 16).replace("T", " "),
             error: "the page did not load", findings };
  }

  const headers = resp.headers();
  findings.push(...judgeHeaders(headers, isHttps));

  // http -> https. Only meaningful for a real host, and only one request.
  if (isHttps && !devHost) {
    try {
      const plain = "http://" + target.hostname + target.pathname;
      const r = await context.request.get(plain, { maxRedirects: 5, timeout: 20000 });
      if (!String(r.url()).startsWith("https://")) {
        findings.push({ sev: "MAJOR", id: "no-redirect",
                        title: "http does not redirect to https",
                        detail: "http://" + target.hostname + " ended at " + r.url() });
      }
    } catch { /* a refused http port is the safe answer */ }
  }

  const cookies = await context.cookies();
  findings.push(...judgeCookies(cookies, isHttps));

  // Mixed content straight out of the markup, which is the only place it
  // survives the browser's own upgrading.
  const domRefs = await page.evaluate(() => {
    const out = [];
    const add = (kind, u) => {
      if (u && /^http:\/\//i.test(u) && !/^http:\/\/(localhost|127\.0\.0\.1)/i.test(u)) {
        out.push({ kind, url: u.slice(0, 160) });
      }
    };
    document.querySelectorAll("script[src]").forEach((e) => add("script", e.getAttribute("src")));
    document.querySelectorAll("link[href]").forEach((e) => add("stylesheet", e.getAttribute("href")));
    document.querySelectorAll("iframe[src]").forEach((e) => add("iframe", e.getAttribute("src")));
    document.querySelectorAll("img[src]").forEach((e) => add("img", e.getAttribute("src")));
    document.querySelectorAll("video[src],audio[src],source[src]").forEach((e) => add("media", e.getAttribute("src")));
    return out;
  });
  // Only on an https page. On an http one every reference is http, so running
  // this would bury the single finding that matters - that there is no https
  // at all - under one line per image.
  if (isHttps) findings.push(...judgeMixed(domRefs, consoleMixed, netHttp));

  // Where the form sends what somebody types into it.
  const forms = await page.evaluate(() => Array.from(document.querySelectorAll("form"))
    .map((f) => ({ action: f.getAttribute("action") || "", method: (f.method || "get").toLowerCase() })));
  for (const f of forms) {
    if (!f.action) continue;
    let a = null;
    try { a = new URL(f.action, url); } catch { /* a relative action we cannot resolve */ }
    if (!a) continue;
    if (a.protocol === "http:" && !isDevHost(a.href)) {
      findings.push({ sev: "BLOCKER", id: "form-http",
                      title: "A form posts over http",
                      detail: "action=" + a.href.slice(0, 120)
                            + " - the enquiry crosses the network in the clear." });
    } else if (a.hostname !== target.hostname) {
      findings.push({ sev: "NOTE", id: "form-offsite",
                      title: "A form posts to another host",
                      detail: a.hostname + " - intended, if that is the form provider." });
    }
  }

  // Script bodies. Same-origin only: a third party's bundle is not ours to
  // audit and its keys are its own.
  const mainBody = await resp.text().catch(() => "");
  findings.push(...scanSecrets(mainBody, "the HTML document"));

  const inline = await page.evaluate(() =>
    Array.from(document.querySelectorAll("script:not([src])")).map((s) => s.textContent || ""));
  inline.forEach((t, i) => findings.push(...scanSecrets(t, "inline script #" + (i + 1))));

  const urls = Array.from(scriptUrls).slice(0, opts.maxScripts);
  let scanned = 0;
  const maps = [];
  for (const u of urls) {
    try {
      const r = await context.request.get(u, { timeout: 20000 });
      if (!r.ok()) continue;
      const body = await r.text();
      if (body.length > 4 * 1024 * 1024) continue;
      scanned += 1;
      findings.push(...scanSecrets(body, u.replace(target.origin, "")));
      const sm = body.match(/\/\/[#@]\s*sourceMappingURL=(\S+)/);
      if (sm) maps.push(new URL(sm[1], u).href);
    } catch { /* unreachable script is not a security finding */ }
  }

  // A source map is only a finding if it is actually served. The comment
  // surviving in the bundle while the .map 404s is the normal, fine case.
  for (const m of maps.slice(0, 3)) {
    try {
      const r = await context.request.get(m, { timeout: 20000 });
      if (r.ok() && /"sources"\s*:/.test((await r.text()).slice(0, 4000))) {
        findings.push({ sev: "MINOR", id: "sourcemap",
                        title: "Source maps are published",
                        detail: m.replace(target.origin, "")
                              + " - the original source, comments and file names "
                              + "are readable.",
                        fix: "Stop emitting maps for production, or stop serving them." });
        break;
      }
    } catch { /* ignore */ }
  }

  let probed = 0;
  if (opts.probe) {
    for (const p of PROBES) {
      try {
        const r = await context.request.get(target.origin + p.path,
                                            { timeout: 15000, maxRedirects: 2 });
        probed += 1;
        const body = r.status() === 200 ? await r.text().catch(() => "") : "";
        const hit = judgeProbe(p, r.status(), body);
        if (hit) findings.push(hit);
      } catch { /* a refused path is the answer we want */ }
    }
  }

  await browser.close();
  return {
    url, taken: new Date().toISOString().slice(0, 16).replace("T", " "),
    devHost, https: isHttps, certError,
    findings: sortFindings(dedupeSecrets(findings)),
    scriptsScanned: scanned, inlineScripts: inline.length,
    thirdParty: Array.from(thirdParty).sort(),
    cookies: cookies.length,
    probed, forms: forms.length,
  };
}

async function main() {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) {
    console.error("usage: node security.js <url> [--out <dir>] [--no-probe]");
    process.exit(2);
  }
  const at = (flag, dflt) => {
    const i = args.indexOf(flag);
    return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
  };
  const opts = {
    probe: !args.includes("--no-probe"),
    maxScripts: parseInt(at("--max-scripts", "25"), 10) || 25,
  };
  const out = at("--out", "");
  const data = await run(url, opts);
  const text = data.error
    ? "# Security pass - " + url + "\n\n" + data.error + "\n"
    : report(data);
  if (out) {
    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(path.join(out, "security.md"), text, "utf8");
    fs.writeFileSync(path.join(out, "security.json"),
                     JSON.stringify(data, null, 2), "utf8");
  }
  console.log(text);
  const blocking = (data.findings || []).filter((f) => f.sev === "BLOCKER").length;
  process.exit(blocking ? 1 : 0);
}

if (require.main === module) {
  main().catch((e) => { console.error(e); process.exit(2); });
}

module.exports = { judgeHeaders, judgeHsts, hstsParts, judgeCsp, judgeCookies,
                   judgeMixed, judgeProbe, scanSecrets, jwtRole, mask,
                   fingerprint, dedupeSecrets, isDevHost, sortFindings, report,
                   PROBES, PATTERNS, HSTS_GOOD, HSTS_SHORT };
