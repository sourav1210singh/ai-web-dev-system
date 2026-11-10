/**
 * Does the analytics pass notice a tag that is declared and silent, a page
 * view counted twice, and a lead's email on its way to a pixel?
 *
 * The fixture requests local URLs shaped like the real collectors, so the
 * detection runs for real and nothing leaves this machine.
 *
 *   node analyticstest.js
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

const page = (body, head) => `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fixture</title>${head || ""}</head><body>${body}</body></html>`;

// A path that contains the collector's hostname matches the same patterns the
// real thing does, without leaving the machine.
const hit = (q) => `/google-analytics.com/g/collect?${q}`;

const PAGES = {
  "/silent": page("<h1>Silent</h1>",
    `<script>window.ga4id="G-SILENT123";/* declared, never sends */</script>`),
  "/double": page("<h1>Double</h1>" +
    `<script>
      // Two identical URLs get coalesced by the browser, and a real GA4
      // hit always carries a random _p, so the fixture has to differ too or
      // it tests the cache rather than the counting.
      new Image().src = "${hit("v=2&tid=G-DOUBLE1&en=page_view&_p=111")}";
      new Image().src = "${hit("v=2&tid=G-DOUBLE1&en=page_view&_p=222")}";
    </script>`,
    `<script>window.id="G-DOUBLE1";</script>`),
  "/pii": page("<h1>Leak</h1>" +
    `<script>
      new Image().src = "${hit("v=2&tid=G-LEAK123&en=generate_lead&em=jo%40client.example&ph=447700900123")}";
    </script>`,
    `<script>window.id="G-LEAK123";</script>`),
  "/consent": page("<h1>Consent</h1>",
    `<script>
      gtag = function(){};
      gtag('consent', 'default', { 'analytics_storage': 'denied' });
      window.id = "G-CONSENT1";
    </script>`),
  "/clean": page("<h1>Clean</h1>" +
    `<script>new Image().src = "${hit("v=2&tid=G-CLEAN123&en=page_view")}";</script>` +
    `<button id="cta">Send</button>` +
    `<script>document.getElementById("cta").onclick = function () {
       new Image().src = "${hit("v=2&tid=G-CLEAN123&en=generate_lead")}";
     };</script>`,
    `<script>window.id="G-CLEAN123";</script>`),
  "/deadend": page("<h1>Dead end</h1><button id='cta'>Send</button>" +
    `<script>new Image().src = "${hit("v=2&tid=G-DEAD1&en=page_view")}";</script>`,
    `<script>window.id="G-DEAD1";</script>`),
};

function serve() {
  const server = http.createServer((req, res) => {
    const u = req.url.split("?")[0];
    if (u.includes("google-analytics.com")) {
      res.writeHead(200, { "Content-Type": "image/gif" });
      return res.end(Buffer.from("R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==", "base64"));
    }
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(PAGES[u] || PAGES["/clean"]);
  });
  return new Promise((r) => server.listen(0, "127.0.0.1",
    () => r({ server, port: server.address().port })));
}

function run(args) {
  return new Promise((resolve) => {
    const p = spawn(process.execPath, [path.join(HERE, "analytics.js"), ...args],
      { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    p.stdout.on("data", (d) => { out += d; });
    p.stderr.on("data", (d) => { out += d; });
    p.on("close", (code) => resolve({ code, out }));
    p.on("error", (e) => resolve({ code: -1, out: String(e) }));
  });
}

(async () => {
  const m = require(path.join(HERE, "analytics.js"));

  // --- the pure parts ---------------------------------------------------
  ok("a GA4 collect URL is recognised as a hit",
     (m.vendorOf("https://www.google-analytics.com/g/collect?v=2") || {}).kind === "hit");
  ok("loading gtag.js is a library, not a hit",
     (m.vendorOf("https://www.googletagmanager.com/gtag/js?id=G-X") || {}).kind === "lib");
  ok("a Meta pixel hit is recognised",
     (m.vendorOf("https://www.facebook.com/tr?id=1&ev=Lead") || {}).id === "meta");
  ok("an ordinary asset is not an analytics request",
     m.vendorOf("https://example.test/logo.png") === null);
  ok("the measurement id is read off the hit",
     m.measurementId("https://x/g/collect?v=2&tid=G-ABC123&en=x") === "G-ABC123");
  ok("the event name is read off the hit",
     m.eventName("https://x/g/collect?en=generate_lead", null) === "generate_lead");
  ok("a Meta event name is read too",
     m.eventName("https://www.facebook.com/tr?id=1&ev=Lead", null) === "Lead");

  const leak = m.personalData("https://x/g/collect?em=jo%40client.example", null);
  ok("an email in a pixel request is a blocker",
     leak.some((p) => p.sev === "BLOCKER"), JSON.stringify(leak).slice(0, 70));
  const hashed = m.personalData(
    "https://www.facebook.com/tr?id=1&ev=Lead&em=" + "a".repeat(64), null);
  ok("a hashed email is reported, and not as plaintext",
     hashed.some((p) => /sha256/.test(p.what)) &&
     !hashed.some((p) => p.sev === "BLOCKER" && /email address/.test(p.what)),
     hashed.map((p) => p.sev).join(","));
  ok("a clean hit carries nothing personal",
     m.personalData("https://x/g/collect?v=2&tid=G-A1&en=page_view&sid=12345678", null)
       .length === 0,
     JSON.stringify(m.personalData("https://x/g/collect?v=2&tid=G-A1&en=page_view&sid=12345678", null)));

  const { server, port } = await serve();
  const base = `http://127.0.0.1:${port}`;
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "antest-"));
  const read = (d) => JSON.parse(fs.readFileSync(path.join(d, "analytics.json"), "utf8"));
  const titles = (d) => (d.findings || []).map((f) => f.title).join(" | ");

  try {
    // --- declared and silent, which is the whole point ------------------
    let dir = path.join(tmp, "silent");
    let r = await run([base + "/silent", "--out", dir, "--width", "390"]);
    ok("the silent page produced a report", fs.existsSync(path.join(dir, "analytics.json")),
       r.out.slice(-150));
    let d = read(dir);
    ok("a GA4 id that is declared and never sends is a blocker",
       /sent nothing/i.test(titles(d)), titles(d).slice(0, 80));
    ok("the declared id is named", (d.declared.ga4 || []).includes("G-SILENT123"),
       (d.declared.ga4 || []).join(","));
    ok("a page with a dead tag exits non-zero", r.code === 1, String(r.code));

    // --- counted twice ---------------------------------------------------
    dir = path.join(tmp, "double");
    await run([base + "/double", "--out", dir, "--width", "390"]);
    d = read(dir);
    ok("two page views to one property is a blocker",
       /counted more than once/i.test(titles(d)), titles(d).slice(0, 80));

    // --- the lead's own data on its way out -------------------------------
    dir = path.join(tmp, "pii");
    await run([base + "/pii", "--out", dir, "--width", "390"]);
    d = read(dir);
    ok("an email heading for a collector is found",
       /email address/i.test(titles(d)), titles(d).slice(0, 90));
    ok("the parameter names are reported too",
       /parameters named/i.test(titles(d)));

    // --- consent that is never granted ------------------------------------
    dir = path.join(tmp, "consent");
    await run([base + "/consent", "--out", dir, "--width", "390"]);
    d = read(dir);
    ok("consent denied and never updated is a blocker",
       /never granted/i.test(titles(d)), titles(d).slice(0, 80));

    // --- a page that is actually fine -------------------------------------
    dir = path.join(tmp, "clean");
    r = await run([base + "/clean", "--out", dir, "--width", "390"]);
    d = read(dir);
    ok("one page view to one property raises nothing",
       !(d.findings || []).some((f) => f.sev !== "CHECK"), titles(d));
    ok("the hit it did send is listed",
       (d.hits || []).some((h) => h.tid === "G-CLEAN123" && h.event === "page_view"));
    ok("a clean page exits zero", r.code === 0, String(r.code));

    // --- the conversion, which is the number the client watches -----------
    dir = path.join(tmp, "click-ok");
    await run([base + "/clean", "--out", dir, "--width", "390", "--click", "#cta"]);
    d = read(dir);
    ok("an event fired by the interaction is reported",
       (d.hits || []).some((h) => h.afterClick && h.event === "generate_lead"),
       (d.hits || []).filter((h) => h.afterClick).map((h) => h.event).join(","));

    dir = path.join(tmp, "click-dead");
    r = await run([base + "/deadend", "--out", dir, "--width", "390", "--click", "#cta"]);
    d = read(dir);
    ok("an interaction that fires nothing is a finding",
       /fired no event/i.test(titles(d)), titles(d).slice(0, 80));

    // --- what the report admits -------------------------------------------
    const text = fs.readFileSync(path.join(tmp, "clean", "analytics.md"), "utf8");
    ok("the report says it read the network, not the markup",
       /not the markup/i.test(text));
    ok("it says a real visitor's blocker changes the numbers",
       /blocker stops some of this/i.test(text));
  } finally {
    server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  const bad = RESULTS.filter((x) => !x).length;
  console.log(`\n${RESULTS.length - bad}/${RESULTS.length} checks passed`);
  process.exit(bad ? 1 : 0);
})();
