/**
 * Does the security pass find what is planted, stay quiet about what is meant
 * to be public, and never copy a secret into its own report?
 *
 * The last one is not a nicety. A report that quotes the key it found has
 * written the leak into the project folder and into whatever the client is
 * sent, so every path that reports a secret is checked for the raw value.
 *
 *   node sectest.js
 */
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const S = require("./security.js");

const RESULTS = [];
function ok(name, cond, extra) {
  RESULTS.push(!!cond);
  console.log(`${cond ? "PASS " : "FAIL "} ${name}${extra ? "  [" + extra + "]" : ""}`);
}
const ids = (list) => (list || []).map((f) => f.id);
const has = (list, id) => ids(list).includes(id);
const sevOf = (list, id) => (list || []).find((f) => f.id === id)?.sev;

// ---------------------------------------------------------------- fixtures

const b64 = (o) => Buffer.from(JSON.stringify(o)).toString("base64url");
const HEAD = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9";
const SIG = "bm90X2FfcmVhbF9zaWduYXR1cmVfYXRfYWxs";
const jwtFor = (role) => HEAD + "." + b64({ role, iss: "supabase", iat: 1 }) + "." + SIG;

const SERVICE_JWT = jwtFor("service_role");   // must be reported
const ANON_JWT = jwtFor("anon");              // must NOT be reported
const PUBLISHABLE = "sb_publishable_" + "A1b2C3d4E5f6G7h8I9j0";   // must NOT be reported
const PLANTED_SB = "sb_secret_" + "9z8y7x6w5v4u3t2s1r0q";
const PLANTED_STRIPE = "sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc";
const PLANTED_AWS = "AKIAIOSFODNN7EXAMPLE";
const PLANTED_GH = "ghp_" + "a".repeat(36);
const PLANTED_GOOGLE = "AIza" + "B".repeat(35);
// Assembled, not written out, for the same reason security.js assembles it:
// the repo's own leak check looks for that exact line.
const PLANTED_PEM = "-----BEGIN RSA PRIVATE KEY" + "-----\nMIIEow==\n";

// ------------------------------------------------------------ pure checks

ok("a localhost origin is a development origin", S.isDevHost("http://localhost:5173/x"));
ok("127.0.0.1 is a development origin", S.isDevHost("http://127.0.0.1:8080/"));
ok("a .test name is a development origin", S.isDevHost("http://shop.test/"));
ok("a client domain is not a development origin",
   !S.isDevHost("https://example.com/") && !S.isDevHost("https://dev-example.com/"));

const hp = S.hstsParts("max-age=63072000; includeSubDomains; preload");
ok("HSTS max-age, includeSubDomains and preload are read",
   hp.maxAge === 63072000 && hp.includeSubDomains && hp.preload);
ok("HSTS with a quoted max-age is still read",
   S.hstsParts('max-age="31536000"').maxAge === 31536000);

ok("a missing HSTS header is reported", has(S.judgeHsts(""), "hsts-missing"));
ok("HSTS with no max-age is reported",
   has(S.judgeHsts("includeSubDomains"), "hsts-no-max-age"));
ok("OWASP's own rollout value is reported as short",
   has(S.judgeHsts("max-age=86400"), "hsts-short"));
ok("the recommended HSTS value is not reported as short",
   !has(S.judgeHsts("max-age=63072000; includeSubDomains; preload"), "hsts-short"));
ok("a year of HSTS is accepted",
   !has(S.judgeHsts("max-age=31536000; includeSubDomains"), "hsts-short"),
   "31536000 is the line");

ok("no CSP at all is reported", has(S.judgeCsp("", ""), "csp-missing"));
ok("a report-only CSP is reported as blocking nothing",
   has(S.judgeCsp("", "default-src 'self'"), "csp-report-only"));
ok("a real CSP is not reported as missing",
   !has(S.judgeCsp("default-src 'self'", ""), "csp-missing"));
ok("a CSP that controls no scripts is reported",
   has(S.judgeCsp("img-src 'self'; style-src 'self'", ""), "csp-no-script-control"));
ok("script-src alone counts as controlling scripts",
   !has(S.judgeCsp("script-src 'self'", ""), "csp-no-script-control"));
ok("unsafe-inline for scripts is reported",
   has(S.judgeCsp("script-src 'self' 'unsafe-inline'", ""), "csp-unsafe-inline"));
ok("unsafe-inline alongside a nonce is not reported",
   !has(S.judgeCsp("script-src 'self' 'unsafe-inline' 'nonce-abc123'", ""),
        "csp-unsafe-inline"),
   "a nonce is the documented way out");
ok("unsafe-eval is reported",
   has(S.judgeCsp("default-src 'self' 'unsafe-eval'", ""), "csp-unsafe-eval"));
ok("unsafe-inline in style-src only is not a script finding",
   !has(S.judgeCsp("script-src 'self'; style-src 'unsafe-inline'", ""),
        "csp-unsafe-inline"));

const bare = S.judgeHeaders({}, true);
ok("a page nothing can frame is reported", has(bare, "framing"));
ok("missing nosniff is reported", has(bare, "nosniff"));
ok("missing Referrer-Policy is reported", has(bare, "referrer-policy"));
ok("X-Frame-Options satisfies the framing check",
   !has(S.judgeHeaders({ "x-frame-options": "SAMEORIGIN" }, true), "framing"));
ok("CSP frame-ancestors satisfies the framing check",
   !has(S.judgeHeaders({ "content-security-policy": "default-src 'self'; frame-ancestors 'none'" }, true),
        "framing"),
   "the modern form of the same control");
ok("a header name in a different case is still read",
   !has(S.judgeHeaders({ "X-Frame-Options": "DENY" }, true), "framing"));
ok("unsafe-url Referrer-Policy is a major finding",
   sevOf(S.judgeHeaders({ "referrer-policy": "unsafe-url" }, true), "referrer-unsafe") === "MAJOR");
ok("HSTS is not demanded of an http origin",
   !ids(S.judgeHeaders({}, false)).some((i) => i.startsWith("hsts")),
   "it would be noise a developer learns to skip");
ok("a versioned Server header is a note, not a defect",
   sevOf(S.judgeHeaders({ server: "nginx/1.18.0" }, true), "server-version") === "NOTE");

const ck = S.judgeCookies([{ name: "PHPSESSID", secure: false, httpOnly: false }], true);
ok("a session cookie without Secure is reported", has(ck, "cookie-insecure"));
ok("a session cookie readable by script is major",
   sevOf(ck, "cookie-no-httponly") === "MAJOR");
ok("an analytics cookie is not expected to be HttpOnly",
   !has(S.judgeCookies([{ name: "_ga", secure: true, httpOnly: false }], true),
        "cookie-no-httponly"),
   "it is read by script on purpose");
const many = S.judgeCookies([{ name: "_ga", secure: false }, { name: "_gid", secure: false },
                             { name: "cookies_ok", secure: false },
                             { name: "django_language", secure: false },
                             { name: "PHPSESSID", secure: false, httpOnly: true }], true);
ok("ordinary cookies without Secure are one grouped finding",
   many.filter((f) => f.id === "cookies-insecure-group").length === 1
   && /4 cookie/.test((many.find((f) => f.id === "cookies-insecure-group") || {}).title || ""),
   "five separate lines pushed the real finding off the top");
ok("the session cookie is still called out on its own",
   many.some((f) => f.id === "cookie-insecure" && /PHPSESSID/.test(f.title)));
ok("SameSite=None without Secure is reported",
   has(S.judgeCookies([{ name: "x", secure: false, sameSite: "None" }], true),
       "cookie-samesite-none"));
ok("cookie flags are not judged on an http origin",
   !has(S.judgeCookies([{ name: "_ga", secure: false, httpOnly: true }], false),
        "cookie-insecure"));

ok("a service_role JWT is decoded", S.jwtRole(SERVICE_JWT) === "service_role");
ok("an anon JWT is decoded", S.jwtRole(ANON_JWT) === "anon");
ok("something that is not a JWT decodes to nothing",
   S.jwtRole("eyJhbGciOi.notbase64.sig") === null && S.jwtRole("") === null);

// --------------------------------------------------- what counts as a leak

const leak = S.scanSecrets(
  "const a='" + PLANTED_SB + "';const b='" + PLANTED_STRIPE + "';" +
  "const c='" + PLANTED_AWS + "';const d='" + PLANTED_GH + "';" +
  "const e='" + SERVICE_JWT + "';const f='" + PLANTED_GOOGLE + "';" +
  PLANTED_PEM, "app.js");
ok("a Supabase secret key is a blocker", sevOf(leak, "supabase-secret") === "BLOCKER");
ok("a Stripe live key is a blocker", sevOf(leak, "stripe-secret") === "BLOCKER");
ok("an AWS access key id is a blocker", sevOf(leak, "aws") === "BLOCKER");
ok("a GitHub token is a blocker", sevOf(leak, "github") === "BLOCKER");
ok("a private key is a blocker", sevOf(leak, "private-key") === "BLOCKER");
ok("a service_role JWT is a blocker", sevOf(leak, "supabase-service-role") === "BLOCKER");
ok("a Google browser key is a minor, not a blocker",
   sevOf(leak, "google-browser-key") === "MINOR",
   "Maps cannot work without it in the page");

const publicOnly = S.scanSecrets(
  "createClient('https://abc.supabase.co','" + PUBLISHABLE + "');" +
  "const legacy='" + ANON_JWT + "';", "app.js");
ok("the Supabase publishable key is not reported", !has(publicOnly, "supabase-secret"));
ok("the legacy anon key is not reported", !has(publicOnly, "supabase-service-role"));
ok("a bundle with only public keys is clean", publicOnly.length === 0,
   "both are documented as safe to expose; flagging them flags every Supabase site");

const dump = JSON.stringify(leak);
ok("the report never carries the Supabase secret", !dump.includes(PLANTED_SB));
ok("the report never carries the Stripe key", !dump.includes(PLANTED_STRIPE));
ok("the report never carries the service_role JWT", !dump.includes(SERVICE_JWT));
ok("the masked sample still identifies the find",
   /^sb_s\.\.\./.test((leak.find((f) => f.id === "supabase-secret") || {}).sample || ""));
ok("masking states the length so it can be recognised",
   /\(\d+ chars\)/.test(S.mask(PLANTED_SB)));
ok("one key repeated is reported once",
   S.scanSecrets([PLANTED_SB, PLANTED_SB, PLANTED_SB].join(" x "), "a.js").length === 1);

const spread = S.dedupeSecrets([
  ...S.scanSecrets("k='" + PLANTED_SB + "'", "a.js"),
  ...S.scanSecrets("k='" + PLANTED_SB + "'", "b.js"),
  ...S.scanSecrets("k='" + PLANTED_SB + "'", "c.js")]);
ok("the same key in three files is one finding", spread.length === 1);
ok("the other files it is in are named",
   spread[0].places === 3 && (spread[0].alsoIn || []).join(",") === "b.js,c.js");

// The reason dedupe fingerprints rather than collapsing on the mask: these two
// keys are different and mask identically.
const twoKeys = S.dedupeSecrets([
  ...S.scanSecrets("a='AIza" + "B".repeat(35) + "'", "a.js"),
  ...S.scanSecrets("b='AIza" + "C".repeat(35) + "'", "a.js")]);
ok("two different keys with the same mask stay two findings", twoKeys.length === 2,
   "collapsing on the mask would have hidden the second");
ok("the fingerprint is not the key itself",
   S.fingerprint(PLANTED_SB).length === 8 && !PLANTED_SB.includes(S.fingerprint(PLANTED_SB)));
ok("a finding with no key is left alone by the dedupe",
   S.dedupeSecrets([{ id: "framing", sev: "MAJOR" }]).length === 1);

// ------------------------------------------------------------ probe logic

const envProbe = S.PROBES.find((p) => p.path === "/.env");
const realEnv = "DATABASE_URL=postgres://u:p@h/db\nSTRIPE_KEY=sk_live_x\n";
const hit = S.judgeProbe(envProbe, 200, realEnv);
ok("a real .env served at 200 is a blocker", hit && hit.sev === "BLOCKER");
ok("the .env finding does not reproduce the file",
   hit && !JSON.stringify(hit).includes("postgres://") && !JSON.stringify(hit).includes("sk_live_x"),
   "it is the thing being protected");
ok("a 200 that is really the app's HTML is not a breach",
   (S.judgeProbe(envProbe, 200, '<!doctype html><html><div id="root"></div>') || {}).sev === "NOTE",
   "a catch-all route answers 200 for every unknown path");
ok("a 404 is no finding at all", S.judgeProbe(envProbe, 404, "Not found") === null);
ok("a git config is recognised by its content",
   (S.judgeProbe(S.PROBES.find((p) => p.path === "/.git/config"), 200,
                 "[core]\n\trepositoryformatversion = 0\n") || {}).sev === "BLOCKER");
ok("a wp-config backup is recognised by its credentials keys",
   (S.judgeProbe(S.PROBES.find((p) => p.path === "/wp-config.php.bak"), 200,
                 "<?php define('DB_PASSWORD', 'x');") || {}).sev === "BLOCKER");
ok("the probe list stays short and fixed", S.PROBES.length === 7,
   "a longer list makes this a scanner, which is not what it is for");

// ---------------------------------------------------------- mixed content

const mActive = S.judgeMixed([{ kind: "script", url: "http://cdn.example.com/a.js" }], [], []);
ok("an http script on an https page is a blocker",
   sevOf(mActive, "mixed-active") === "BLOCKER");
ok("an http image is major, not a blocker",
   sevOf(S.judgeMixed([{ kind: "img", url: "http://x.example/a.jpg" }], [], []),
         "mixed-passive") === "MAJOR");
ok("an http request with nothing in the markup is still reported",
   has(S.judgeMixed([], [], ["http://x.example/beacon"]), "mixed-network"),
   "it came from script");
ok("the browser's own mixed-content warning is reported when nothing else saw it",
   has(S.judgeMixed([], ["Mixed Content: The page was loaded over HTTPS"], []),
       "mixed-console"));
ok("a clean page reports no mixed content", S.judgeMixed([], [], []).length === 0);

const sorted = S.sortFindings([{ sev: "NOTE", title: "n" }, { sev: "BLOCKER", title: "b" },
                               { sev: "MINOR", title: "m" }, { sev: "MAJOR", title: "j" }]);
ok("findings come out worst first",
   sorted.map((f) => f.sev).join(",") === "BLOCKER,MAJOR,MINOR,NOTE");

const txt = S.report({ url: "https://x.example", taken: "now", devHost: false,
                       findings: [{ sev: "BLOCKER", title: "t", detail: "d" }],
                       thirdParty: ["a.example"], scriptsScanned: 2, cookies: 1, probed: 7 });
ok("the report counts the blockers", /1 blocker/.test(txt));
ok("the report states its own limits", /not a penetration test/.test(txt));
ok("the report names the third parties that can change the page",
   /a\.example/.test(txt) && /can change this page/.test(txt));
ok("a development origin is explained rather than failed",
   /skipped rather than failed/.test(
     S.report({ url: "http://localhost", taken: "now", devHost: true, findings: [] })));

// -------------------------------------------------------- against a page

const LEAKY = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Leaky</title></head><body>
<h1>Leaky</h1>
<form action="http://insecure.invalid/post" method="post">
  <input name="email"><button>Send</button>
</form>
<script>window.__cfg = { key: "${PLANTED_SB}" };</script>
<script src="/app.js"></script>
</body></html>`;

const CLEAN = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Clean</title></head><body>
<h1>Clean</h1>
<form action="/enquiry" method="post"><input name="email"><button>Send</button></form>
<script src="/clean.js"></script>
</body></html>`;

// Only the keys documented as safe to expose, plus a sourceMappingURL whose
// map really is served.
const APP_JS = `var sb = "${PUBLISHABLE}"; var legacy = "${ANON_JWT}";
var lift = "${SERVICE_JWT}";
//# sourceMappingURL=/app.js.map`;
const CLEAN_JS = `var sb = "${PUBLISHABLE}"; console.log(sb.length);`;
const APP_MAP = JSON.stringify({ version: 3, sources: ["src/main.ts"], mappings: "" });

function serve() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const send = (code, type, body) => {
        res.writeHead(code, { "content-type": type });
        res.end(body);
      };
      if (req.url === "/leaky") return send(200, "text/html; charset=utf-8", LEAKY);
      if (req.url === "/clean") return send(200, "text/html; charset=utf-8", CLEAN);
      if (req.url === "/app.js") return send(200, "application/javascript", APP_JS);
      if (req.url === "/clean.js") return send(200, "application/javascript", CLEAN_JS);
      if (req.url === "/app.js.map") return send(200, "application/json", APP_MAP);
      // Everything else answers with the app's own HTML, exactly like a
      // single-page app, so the probe discrimination is exercised for real.
      return send(200, "text/html; charset=utf-8",
                  '<!doctype html><html><body><div id="root"></div></body></html>');
    });
    srv.listen(0, "127.0.0.1", () => resolve({ srv, port: srv.address().port }));
  });
}

function runCli(url, out) {
  return new Promise((resolve) => {
    // spawn, not execFileSync: the fixture server runs in this process and a
    // blocking call stops it answering, which looks exactly like a browser
    // fault and wasted an afternoon the last time.
    const p = spawn(process.execPath, [path.join(__dirname, "security.js"), url,
                                       "--out", out],
                    { stdio: ["ignore", "pipe", "pipe"] });
    let so = "", se = "";
    p.stdout.on("data", (d) => { so += d; });
    p.stderr.on("data", (d) => { se += d; });
    p.on("close", (code) => resolve({ code, so, se }));
  });
}

(async () => {
  const { srv, port } = await serve();
  const out = fs.mkdtempSync(path.join(os.tmpdir(), "sectest-"));
  try {
    const base = "http://127.0.0.1:" + port;
    const r = await runCli(base + "/leaky", out);
    const jf = path.join(out, "security.json");
    ok("the pass writes a json report", fs.existsSync(jf), r.se.slice(0, 160));
    const d = fs.existsSync(jf) ? JSON.parse(fs.readFileSync(jf, "utf8")) : { findings: [] };
    const md = fs.existsSync(path.join(out, "security.md"))
      ? fs.readFileSync(path.join(out, "security.md"), "utf8") : "";

    ok("a development origin is not reported as having no https",
       !has(d.findings, "no-https") && !ids(d.findings).some((i) => i.startsWith("hsts")),
       "http on 127.0.0.1 is expected, not a defect");
    // An inline script's text is part of the HTML document, so the document
    // scan reaches it first and the inline hit folds into that same finding as
    // a second location. One line, both places named.
    const inlineHit = (d.findings || []).find((f) => f.id === "supabase-secret");
    ok("a secret in an inline script is found", !!inlineHit,
       inlineHit ? inlineHit.where : "not found at all");
    ok("it is reported once, naming the inline block as well",
       inlineHit && (inlineHit.alsoIn || []).some((w) => /inline script/.test(w)),
       inlineHit ? JSON.stringify(inlineHit.alsoIn) : "-");
    ok("a service_role key in the bundle is found and the file named",
       (d.findings || []).some((f) => f.id === "supabase-service-role"
                                   && /app\.js/.test(f.where || "")));
    ok("the publishable key in the same bundle is not reported",
       !(d.findings || []).some((f) => /publishable/i.test(JSON.stringify(f))));
    ok("a form posting over http is a blocker",
       sevOf(d.findings, "form-http") === "BLOCKER");
    ok("a served source map is reported", has(d.findings, "sourcemap"));
    ok("the catch-all 200s are not reported as breaches",
       !ids(d.findings).some((i) => i.startsWith("probe-/")) &&
       (d.findings || []).some((f) => f.id === "probe-catchall"),
       "seven paths answered 200 with the app's HTML");
    ok("the probes all ran", d.probed === 7);
    ok("a blocker makes the tool exit non-zero", r.code === 1, "exit " + r.code);
    ok("neither report file carries the planted secret",
       !md.includes(PLANTED_SB) && !JSON.stringify(d).includes(PLANTED_SB)
       && !md.includes(SERVICE_JWT),
       "the whole point of masking");

    const out2 = fs.mkdtempSync(path.join(os.tmpdir(), "sectest2-"));
    const r2 = await runCli(base + "/clean", out2);
    const d2 = JSON.parse(fs.readFileSync(path.join(out2, "security.json"), "utf8"));
    const blockers = (d2.findings || []).filter((f) => f.sev === "BLOCKER");
    ok("a clean page has no blockers", blockers.length === 0,
       blockers.map((b) => b.id).join(",") || "none");
    ok("a clean page exits zero", r2.code === 0, "exit " + r2.code);
    ok("a page with no planted key reports no secret at all",
       !(d2.findings || []).some((f) => /supabase|stripe|aws|github|private-key/.test(f.id)));
  } finally {
    srv.close();
  }

  const pass = RESULTS.filter(Boolean).length;
  console.log(`\n${pass}/${RESULTS.length} checks passed`);
  process.exit(pass === RESULTS.length ? 0 : 1);
})();
