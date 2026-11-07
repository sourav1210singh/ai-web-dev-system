/**
 * Does the performance pass find faults that are really there, and stay quiet
 * about a page that has none?
 *
 * Everything is measured against a local page built with the faults put in on
 * purpose - a blocking script, a font with no display, an oversized image, a
 * lazy hero, an uncompressed file and a late layout shift - so a miss is
 * provable rather than arguable. The fixture is a real page served over HTTP,
 * not a hand-written object, because a fixture written from memory tests the
 * memory.
 *
 *   node perftest.js
 */
const fs = require("fs");
const http = require("http");
const os = require("os");
const path = require("path");
const zlib = require("zlib");
const { spawn } = require("child_process");

const HERE = __dirname;
const RESULTS = [];
function ok(name, cond, extra) {
  RESULTS.push(!!cond);
  console.log(`${cond ? "PASS " : "FAIL "} ${name}${extra ? "  [" + extra + "]" : ""}`);
}

// A 1200x1200 PNG, so "shown at 100px" is provably oversized.
function bigPng() {
  const w = 1200, h = 1200;
  const raw = Buffer.alloc((w * 3 + 1) * h);
  for (let y = 0; y < h; y++) raw[y * (w * 3 + 1)] = 0;
  const chunk = (type, data) => {
    const len = Buffer.alloc(4); len.writeUInt32BE(data.length);
    const td = Buffer.concat([Buffer.from(type), data]);
    const crc = Buffer.alloc(4); crc.writeUInt32BE(crc32(td) >>> 0);
    return Buffer.concat([len, td, crc]);
  };
  let table = null;
  function crc32(buf) {
    if (!table) {
      table = [];
      for (let n = 0; n < 256; n++) {
        let c = n;
        for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        table[n] = c;
      }
    }
    let c = 0xffffffff;
    for (const b of buf) c = table[(c ^ b) & 0xff] ^ (c >>> 8);
    return c ^ 0xffffffff;
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4);
  ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr), chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const FAULTY = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Faulty</title>
<style>
 @font-face { font-family: NoDisplay; src: url(/f.woff2) format("woff2"); }
 body { margin:0; font-family: NoDisplay, Arial, sans-serif; }
 h1 { font-size: 40px; margin: 16px; }
 .hero { width: 100px; height: 100px; }
</style>
<script src="/blocking.js"></script>
</head><body>
<h1>Faulty page</h1>
<img class="hero" src="/big.png" loading="lazy" alt="hero">
<p id="copy">Body copy that will be pushed down.</p>
<script>
 setTimeout(function () {
   var d = document.createElement("div");
   d.style.cssText = "height:420px;background:#ddd";
   document.body.insertBefore(d, document.body.firstChild);
 }, 400);
</script>
</body></html>`;

const CLEAN = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Clean</title>
<style>
 @font-face { font-family: Ok; src: url(/f.woff2) format("woff2"); font-display: swap; }
 body { margin:0; font-family: Ok, Arial, sans-serif; }
 h1 { font-size: 40px; margin: 16px; }
</style>
<script src="/blocking.js" defer></script>
</head><body><h1>Clean page</h1><p>Nothing moves.</p></body></html>`;

function serve() {
  const png = bigPng();
  const bigJs = "/*" + "x".repeat(40 * 1024) + "*/\nwindow.ok=1;";
  const server = http.createServer((req, res) => {
    const u = req.url.split("?")[0];
    const send = (type, body, headers) => {
      res.writeHead(200, { "Content-Type": type, "Cache-Control": "no-store",
                           ...(headers || {}) });
      res.end(body);
    };
    if (u === "/big.png") return send("image/png", png);
    // Deliberately uncompressed, which is what the check is for.
    if (u === "/blocking.js") return send("application/javascript", bigJs);
    if (u === "/f.woff2") return send("font/woff2", Buffer.alloc(2048));
    if (u === "/clean") return send("text/html; charset=utf-8", CLEAN);
    return send("text/html; charset=utf-8", FAULTY);
  });
  return new Promise((r) => server.listen(0, "127.0.0.1",
    () => r({ server, port: server.address().port })));
}

function run(args, cwd) {
  return new Promise((resolve) => {
    const p = spawn(process.execPath, [path.join(HERE, "perf.js"), ...args],
      { cwd, stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    p.stdout.on("data", (d) => { out += d; });
    p.stderr.on("data", (d) => { out += d; });
    p.on("close", (code) => resolve({ code, out }));
    p.on("error", (e) => resolve({ code: -1, out: String(e) }));
  });
}

(async () => {
  const m = require(path.join(HERE, "perf.js"));
  const { server, port } = await serve();
  const base = `http://127.0.0.1:${port}`;
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "perftest-"));

  try {
    // --- the thresholds, which end up in client reports -----------------
    ok("LCP target is Google's 2.5s", m.GOOD.lcp === 2500);
    ok("CLS target is 0.1", m.GOOD.cls === 0.1);
    ok("INP target is 200ms", m.GOOD.inp === 200);
    ok("the poor line for LCP is 4s", m.POOR.lcp === 4000);
    ok("a font file is classed as a font, not other",
       m.kindOf("", "https://x.test/a.woff2") === "font");
    ok("an svg is an image", m.kindOf("image/svg+xml", "x") === "image");

    // --- the faulty page -------------------------------------------------
    const faultDir = path.join(tmp, "faulty");
    const r = await run([base + "/", "--out", faultDir, "--width", "390",
                         "--no-throttle"]);
    const jsonPath = path.join(faultDir, "perf.json");
    ok("it produced a report", fs.existsSync(jsonPath), r.out.slice(-200));
    const d = fs.existsSync(jsonPath)
      ? JSON.parse(fs.readFileSync(jsonPath, "utf8")) : {};
    const titles = (d.findings || []).map((f) => f.title).join(" | ");

    ok("the render-blocking script is found",
       /render-blocking script/i.test(titles), titles.slice(0, 90));
    ok("the font with no font-display is found",
       /no font-display/i.test(titles));
    ok("the oversized image is found", /larger than it is shown/i.test(titles));
    ok("the lazy hero is found", /Above-the-fold image is lazy/i.test(titles));
    ok("the uncompressed file is found", /without compression/i.test(titles));
    // Measured: with touch emulation on, Chromium marks every layout shift
    // hadRecentInput even though nothing was clicked, so the spec figure is
    // 0.000 on a page that visibly jumps. Both are kept.
    ok("the late layout shift is measured", (d.clsAll || 0) > 0.05,
       `clsAll ${(d.clsAll || 0).toFixed(3)}, cls ${(d.cls || 0).toFixed(3)}`);
    ok("the shifts the spec would drop are counted, not lost",
       (d.excluded || 0) > 0, `${d.excluded} excluded`);
    ok("the element that shifted is named",
       (d.shifts || []).length > 0 && !!d.shifts[0].el,
       (d.shifts || []).map((s) => s.el).join(","));
    ok("a jumping page is reported as jumping, not as 0.000",
       (d.findings || []).some((f) => /Layout shifts|jumps about/i.test(f.title)),
       (d.findings || []).map((f) => f.title).join(" | ").slice(0, 80));
    ok("the report explains why the two figures differ",
       fs.readFileSync(path.join(faultDir, "perf.md"), "utf8")
         .includes("input-caused"));
    ok("the LCP element is named", !!d.lcpEl, d.lcpEl);
    ok("bytes are split into yours and third party",
       d.firstPartyBytes > 0 && d.thirdPartyBytes === 0,
       `${m.KB(d.firstPartyBytes)}KB / ${m.KB(d.thirdPartyBytes)}KB`);
    ok("the weight is broken down by kind",
       d.byKind && d.byKind.script > 0 && d.byKind.image > 0,
       JSON.stringify(d.byKind));
    ok("a page with faults exits non-zero", r.code === 1, String(r.code));

    // --- the clean page --------------------------------------------------
    const cleanDir = path.join(tmp, "clean");
    const c = await run([base + "/clean", "--out", cleanDir, "--width", "390",
                         "--no-throttle"]);
    const cd = JSON.parse(fs.readFileSync(path.join(cleanDir, "perf.json"), "utf8"));
    const ct = (cd.findings || []).map((f) => f.title).join(" | ");
    ok("a deferred script is not called blocking", !/render-blocking/i.test(ct), ct);
    ok("font-display: swap is accepted", !/no font-display/i.test(ct));
    ok("a page that does not move has no shift finding",
       (cd.clsAll || 0) < 0.05, `clsAll ${(cd.clsAll || 0).toFixed(3)}`);

    // --- the honesty of the report ---------------------------------------
    const text = fs.readFileSync(path.join(faultDir, "perf.md"), "utf8");
    ok("the report says these are lab numbers",
       /lab/i.test(text) && /75th percentile/i.test(text));
    ok("it says a lab pass is not a Search Console pass",
       /not a pass in Search Console/i.test(text));
    ok("an unthrottled run says so in the report",
       /\*\*not throttled\*\*/.test(text));

    // --- the budget is ours, and says so ---------------------------------
    const over = m.findings({ lcp: 0, cls: 0, shifts: [], totalBytes: 5e6,
      firstPartyBytes: 5e6, thirdPartyBytes: 0, thirdParties: [],
      uncompressed: [], blocking: {}, oversized: [], lazyAboveFold: [],
      noCache: [], longTaskTime: 0, longTasks: 0 }, 2048);
    ok("going over the budget is reported", over.some((f) => /budget/i.test(f.title)));
    ok("the budget is labelled as the house's, not a standard",
       over.some((f) => /not a published standard/i.test(f.detail)));

    const quiet = m.findings({ lcp: 1200, cls: 0.01, shifts: [], totalBytes: 5e5,
      firstPartyBytes: 5e5, thirdPartyBytes: 0, thirdParties: [],
      uncompressed: [], blocking: {}, oversized: [], lazyAboveFold: [],
      noCache: [], longTaskTime: 0, longTasks: 0 }, 2048);
    ok("a fast page produces no findings at all", quiet.length === 0,
       quiet.map((f) => f.title).join(","));
  } finally {
    server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  const bad = RESULTS.filter((x) => !x).length;
  console.log(`\n${RESULTS.length - bad}/${RESULTS.length} checks passed`);
  process.exit(bad ? 1 : 0);
})();
