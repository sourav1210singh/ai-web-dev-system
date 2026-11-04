/**
 * Does the responsive pass actually look at the widths it claims to?
 *
 * Serves a fixture whose fault is width-dependent on purpose - a block 2000px
 * wide, which overflows a phone and a laptop and fits a 2560 monitor - then
 * runs both scripts against it and reads what came back. That is the bug this
 * suite exists for: a sweep that stops at 1440 reports a page as fine when the
 * only width that would have shown the problem was never opened.
 *
 *   node qatest.js
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

const PAGE = `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fixture</title><style>
 body{margin:0;font-family:Arial,sans-serif;background:#ffffff}
 h1{font-size:40px;font-weight:700;margin:16px}
 .wide{width:2000px;height:60px;background:#cccccc}
 .mid{width:700px;height:60px;background:#dddddd}
 .ok{width:100%;height:60px;background:#eeeeee}
</style></head><body>
<header><img src="data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==" alt="logo" width="40" height="40"></header>
<h1>Fixture heading</h1>
<div class="CLASS"></div>
</body></html>`;

function serve() {
  const server = http.createServer((req, res) => {
    const cls = req.url.startsWith("/wide") ? "wide"
              : req.url.startsWith("/mid") ? "mid" : "ok";
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(PAGE.replace("CLASS", cls));
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1",
    () => resolve({ server, port: server.address().port })));
}

/**
 * Run a script and wait for it WITHOUT blocking this process.
 *
 * execFileSync blocks the event loop, and the fixture server lives in this
 * process, so every page load timed out: the browsers were asking a server
 * that could not answer until the browsers finished. The failure looked like
 * a browser problem and was this function.
 */
function run(script, args, cwd) {
  return new Promise((resolve) => {
    const p = spawn(process.execPath, [path.join(HERE, script), ...args],
      { cwd, stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    p.stdout.on("data", (d) => { out += d; });
    p.stderr.on("data", (d) => { out += d; });
    p.on("close", (code) => resolve({ code, out }));
    p.on("error", (e) => resolve({ code: -1, out: String(e) }));
  });
}

(async () => {
  const { server, port } = await serve();
  const base = `http://127.0.0.1:${port}`;
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "qatest-"));
  try {
    // --- the defaults, which is what today's bug was about ----------------
    const rqaSrc = fs.readFileSync(path.join(HERE, "rqa.js"), "utf8");
    const defaults = (rqaSrc.match(/DEFAULT_WIDTHS = \[([^\]]*)\]/) || [])[1] || "";
    ok("the responsive sweep reaches past 2000px",
       defaults.split(",").some((w) => Number(w) >= 2000), defaults.trim());
    ok("every swept width has a real viewport height",
       defaults.split(",").map(Number).filter(Boolean)
         .every((w) => new RegExp(`${w}\\s*:\\s*\\d+`).test(rqaSrc)), defaults.trim());

    const cbSrc = fs.readFileSync(path.join(HERE, "crossbrowser.js"), "utf8");
    const cbw = (cbSrc.match(/DEFAULT_WIDTHS = \[([^\]]*)\]/) || [])[1] || "";
    ok("the cross-browser pass reaches past 2000px too",
       cbw.split(",").some((w) => Number(w) >= 2000), cbw.trim());

    // --- rqa against a fault that only some widths can see ----------------
    const rqaOut = path.join(tmp, "rqa");
    const r = await run("rqa.js", [base + "/wide", "--out", rqaOut,
                             "--widths", "390,2560"]);
    const findings = path.join(rqaOut, "findings.json");
    ok("rqa.js produced findings", fs.existsSync(findings), r.out.slice(-160));
    if (fs.existsSync(findings)) {
      const data = JSON.parse(fs.readFileSync(findings, "utf8"));
      const vps = data.viewports || [];
      ok("it opened both widths it was given", vps.length === 2,
         vps.map((v) => v.width).join(","));
      const at = (w) => (vps.find((v) => v.width === w) || {}).findings || [];
      const over = (w) => at(w).some(
        (f) => /overflow/i.test(f.kind || "") || /scrolls sideways/i.test(f.msg || ""));
      ok("the 2000px block is reported as overflow on a phone", over(390),
         at(390).map((f) => f.kind).slice(0, 3).join(" | "));
      ok("the same block does not overflow a 2560 monitor", !over(2560),
         at(2560).map((f) => f.kind).slice(0, 3).join(" | "));
      ok("a screenshot exists for every width opened",
         vps.every((v) => fs.readdirSync(rqaOut)
           .some((f) => f.includes(String(v.width)) && f.endsWith(".png"))),
         fs.readdirSync(rqaOut).filter((f) => f.endsWith(".png")).join(","));
    }

    // A 700px block on a 390px phone is the ordinary case, and it was being
    // missed: the browser zooms out to fit the overflow, window.innerWidth
    // grows with it, and the comparison against it comes out false. Anything
    // between roughly 400px and 1500px went unreported.
    const midOut = path.join(tmp, "mid");
    await run("rqa.js", [base + "/mid", "--out", midOut, "--widths", "390"]);
    const midFile = path.join(midOut, "findings.json");
    ok("a 700px block on a phone is reported, not zoomed away",
       fs.existsSync(midFile) && JSON.parse(fs.readFileSync(midFile, "utf8"))
         .viewports[0].findings.some((f) => /overflow/i.test(f.kind || "")),
       fs.existsSync(midFile)
         ? JSON.parse(fs.readFileSync(midFile, "utf8")).viewports[0]
             .findings.map((f) => f.kind).join(",") || "nothing found"
         : "no findings file");

    // --- the three-engine pass -------------------------------------------
    const cbOut = path.join(tmp, "cb");
    const c = await run("crossbrowser.js", [base, "--routes", "/", "--widths", "390,1440",
                                      "--out", cbOut]);
    const rep = path.join(cbOut, "report.json");
    ok("the cross-browser pass produced a report", fs.existsSync(rep),
       (c.out || "").slice(-200));
    if (fs.existsSync(rep)) {
      const data = JSON.parse(fs.readFileSync(rep, "utf8"));
      const engines = [...new Set(data.rows.filter((x) => !x.error)
                                           .map((x) => x.engine))];
      ok("it opened the page in all three engines", engines.length === 3,
         engines.join(","));
      ok("it opened every width in every engine",
         data.rows.filter((x) => !x.error).length === 6,
         String(data.rows.filter((x) => !x.error).length) + " of 6");
      ok("a clean page reports no difference between engines",
         data.differences.length === 0,
         data.differences.map((d) => d.what).join(" | "));
      ok("it exits 0 when the engines agree", c.code === 0, String(c.code));
      ok("every row carries the width it was measured at",
         data.rows.filter((x) => !x.error).every((x) => x.width > 0));
    }

    // --- a real difference must be reported ------------------------------
    const diffSrc = fs.readFileSync(path.join(HERE, "crossbrowser.js"), "utf8");
    const fn = diffSrc.slice(diffSrc.indexOf("function differences"),
                             diffSrc.indexOf("(async () =>"));
    const differences = new Function(fn + "; return differences;")();
    const same = { route: "/", width: 390, h1: { size: 40, weight: "700", family: "Arial" },
                   logo: { src: "a.png" }, status: 200, overflows: false,
                   brokenImages: 0, bodyBg: "rgb(255, 255, 255)" };
    ok("identical measurements are not reported as a difference",
       differences([{ ...same, engine: "chromium" },
                    { ...same, engine: "firefox" }]).length === 0);
    const d = differences([{ ...same, engine: "chromium" },
                           { ...same, engine: "webkit", h1: { ...same.h1, size: 28 } }]);
    ok("a real h1 difference is reported with both values",
       d.length === 1 && /40/.test(d[0].by) && /28/.test(d[0].by),
       d.map((x) => x.by).join(" | "));
    ok("one engine alone is never compared against itself",
       differences([{ ...same, engine: "chromium" }]).length === 0);
  } finally {
    server.close();
    fs.rmSync(tmp, { recursive: true, force: true });
  }

  const bad = RESULTS.filter((r) => !r).length;
  console.log(`\n${RESULTS.length - bad}/${RESULTS.length} checks passed`);
  process.exit(bad ? 1 : 0);
})();
