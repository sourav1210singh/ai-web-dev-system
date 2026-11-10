/**
 * Does the accessibility pass find the faults a rule engine misses, and stay
 * quiet about a page that has none?
 *
 * Two local pages, one with each fault planted on purpose and one without, so
 * a miss is provable. The checks that matter most here are the ones axe does
 * not make: a skip link that points nowhere, a missing landmark, a heading
 * jump, something focusable hidden from assistive technology, and focus with
 * no visible style.
 *
 *   node a11ytest.js
 */
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const { spawn } = require("child_process");

const HERE = __dirname;
const RESULTS = [];
function ok(name, cond, extra) {
  RESULTS.push(!!cond);
  console.log(`${cond ? "PASS " : "FAIL "} ${name}${extra ? "  [" + extra + "]" : ""}`);
}

const FAULTY = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Faulty</title>
<style>
 body{margin:0;font-family:Arial,sans-serif}
 /* The most common accessibility defect there is, and no rule engine
    reports it: focus removed and nothing put back. */
 a,button{outline:none}
 nav{padding:8px}
</style></head>
<body>
<a href="#nowhere">Skip to content</a>
<nav><a href="/a">One</a></nav>
<nav><a href="/b">Two</a></nav>
<h1>Faulty page</h1>
<h3>Jumped a level</h3>
<div aria-hidden="true"><button id="ghost">Hidden but reachable</button></div>
<button id="nameless"></button>
<img src="data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==">
<p>Body copy.</p>
</body></html>`;

const CLEAN = `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clean</title>
<style>
 body{margin:0;font-family:Arial,sans-serif;color:#111;background:#fff}
 a:focus,button:focus{outline:3px solid #0b5fff;outline-offset:2px}
 nav{padding:8px}
</style></head>
<body>
<a class="skip" href="#main">Skip to content</a>
<header><nav aria-label="Primary"><a href="/a">One</a></nav></header>
<main id="main">
  <h1>Clean page</h1>
  <h2>A second level</h2>
  <button type="button">A named button</button>
  <img src="data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==" alt="A dot">
  <p>Body copy.</p>
</main>
<footer><p>Footer.</p></footer>
</body></html>`;

function serve() {
  const server = http.createServer((req, res) => {
    const clean = req.url.startsWith("/clean");
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(clean ? CLEAN : FAULTY);
  });
  return new Promise((r) => server.listen(0, "127.0.0.1",
    () => r({ server, port: server.address().port })));
}

function run(args) {
  return new Promise((resolve) => {
    const p = spawn(process.execPath, [path.join(HERE, "a11y.js"), ...args],
      { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    p.stdout.on("data", (d) => { out += d; });
    p.stderr.on("data", (d) => { out += d; });
    p.on("close", (code) => resolve({ code, out }));
    p.on("error", (e) => resolve({ code: -1, out: String(e) }));
  });
}

(async () => {
  const m = require(path.join(HERE, "a11y.js"));
  ok("a critical axe impact is a MAJOR", m.severityOf("critical") === "MAJOR");
  ok("a serious axe impact is a MAJOR", m.severityOf("serious") === "MAJOR");
  ok("a minor axe impact is only worth a look", m.severityOf("minor") === "CHECK");

  let axe = null;
  try {
    axe = await m.findAxe("");
    ok("axe-core was found or fetched", !!axe && fs.existsSync(axe.path), axe && axe.from);
  } catch (e) {
    ok("axe-core was found or fetched", false, String(e).slice(0, 80));
  }

  const { server, port } = await serve();
  const base = `http://127.0.0.1:${port}`;
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "a11ytest-"));
  try {
    const faultDir = path.join(tmp, "faulty");
    const r = await run([base, "--routes", "/", "--widths", "390",
                         "--out", faultDir]);
    const jp = path.join(faultDir, "a11y.json");
    ok("it produced a report", fs.existsSync(jp), r.out.slice(-180));
    const d = fs.existsSync(jp) ? JSON.parse(fs.readFileSync(jp, "utf8")) : { rows: [] };
    const row = (d.rows || [])[0] || {};
    const notes = ((row.sr || {}).notes || []);
    const detail = notes.map((n) => `${n.kind}:${n.detail}`).join(" | ");

    ok("a skip link pointing nowhere is found",
       notes.some((n) => n.kind === "skip-link" && /not on the page/.test(n.detail)),
       detail.slice(0, 100));
    ok("the missing main landmark is found",
       notes.some((n) => n.kind === "landmark" && /no main/.test(n.detail)));
    ok("the missing footer landmark is found",
       notes.some((n) => n.kind === "landmark" && /no contentinfo/.test(n.detail)));
    ok("two unnamed navs are reported",
       notes.some((n) => n.kind === "landmark" && /navigation landmarks/.test(n.detail)));
    ok("the heading jump is found",
       notes.some((n) => n.kind === "headings" && /h1 jumps to h3/.test(n.detail)));
    ok("something focusable inside aria-hidden is found",
       notes.some((n) => n.kind === "aria"));
    ok("a button with no accessible name is found",
       notes.some((n) => n.kind === "name"));
    ok("focus with no visible style is found",
       (row.focus || {}).invisible && row.focus.invisible.length > 0,
       `${((row.focus || {}).invisible || []).length} of ${(row.focus || {}).checked}`);
    if (axe) {
      ok("axe ran and its version is recorded", !!row.axeVersion, row.axeVersion);
      ok("the image with no alt is found by axe",
         (row.violations || []).some((v) => /image-alt/.test(v.id)),
         (row.violations || []).map((v) => v.id).join(","));
    }
    ok("a page with faults exits non-zero", r.code === 1, String(r.code));

    // --- the clean page --------------------------------------------------
    const cleanDir = path.join(tmp, "clean");
    const c = await run([base + "/clean", "--routes", "/clean", "--widths", "390",
                         "--out", cleanDir]);
    const cd = JSON.parse(fs.readFileSync(path.join(cleanDir, "a11y.json"), "utf8"));
    const crow = (cd.rows || [])[0] || {};
    const cnotes = ((crow.sr || {}).notes || []).filter((n) => n.sev === "MAJOR");
    ok("a correct page raises no major note",
       cnotes.length === 0,
       cnotes.map((n) => `${n.kind}:${n.detail}`).join(" | "));
    ok("a visible focus outline is accepted",
       ((crow.focus || {}).invisible || []).length === 0,
       ((crow.focus || {}).invisible || []).join(","));
    ok("a correct page exits zero", c.code === 0, String(c.code));

    // --- what the report admits ------------------------------------------
    const text = fs.readFileSync(path.join(faultDir, "a11y.md"), "utf8");
    ok("the report says axe only covers part of WCAG",
       /third to a half/.test(text));
    ok("it names what still needs a person",
       /reading order/.test(text) && /out of context/.test(text));
    ok("the width is in the report", /390px/.test(text));
  } finally {
    server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  const bad = RESULTS.filter((x) => !x).length;
  console.log(`\n${RESULTS.length - bad}/${RESULTS.length} checks passed`);
  process.exit(bad ? 1 : 0);
})();
