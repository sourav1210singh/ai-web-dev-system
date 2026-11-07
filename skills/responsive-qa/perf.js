/**
 * What the page costs to load, measured rather than guessed.
 *
 *   node perf.js <url> [--out <dir>] [--width 390] [--budget-kb 2048]
 *                      [--no-throttle]
 *
 * Opens the page once with a cold cache on a throttled connection and a
 * throttled CPU, and records what arrived, what blocked, and what moved.
 *
 * **This is a lab measurement, and a lab measurement is not Core Web Vitals.**
 * Google's thresholds - LCP 2.5s, INP 200ms, CLS 0.1 - are defined at the 75th
 * percentile of real visitors over 28 days. One run on this machine tells you
 * what this machine saw. It is enough to find the fault and cheap enough to
 * run on every build; it is not the number that decides whether the site
 * passes. For that, read the field data in Search Console.
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

// Google's own numbers, from web.dev/articles/vitals. They apply to field data
// at the 75th percentile; they are used here as the line above which a lab run
// is definitely worth investigating, not as a verdict.
const GOOD = { lcp: 2500, cls: 0.1, inp: 200 };
const POOR = { lcp: 4000, cls: 0.25, inp: 500 };

// Roughly Lighthouse's mobile preset. Without it a page measured on a fast
// desktop over a fast line looks fine and ships to somebody on a phone.
const THROTTLE = {
  downloadThroughput: Math.floor((1.6 * 1024 * 1024) / 8),
  uploadThroughput: Math.floor((750 * 1024) / 8),
  latency: 150,
  cpuRate: 4,
};

const KB = (b) => Math.round((b || 0) / 1024);

/** Set up the observers before any of the page's own code runs. */
const COLLECT = () => {
  window.__perf = { lcp: 0, lcpEl: "", cls: 0, clsAll: 0, excluded: 0,
                    shifts: [], longTasks: 0, longTaskTime: 0 };
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        window.__perf.lcp = e.startTime;
        const el = e.element;
        window.__perf.lcpEl = el
          ? el.tagName.toLowerCase() +
            (el.id ? "#" + el.id : "") +
            (el.className && el.className.toString
              ? "." + el.className.toString().trim().split(/\s+/)[0] : "")
          : (e.url || "").split("/").pop();
      }
    }).observe({ type: "largest-contentful-paint", buffered: true });
  } catch (e) { /* not supported */ }
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        // The spec excludes a shift the visitor caused, and that is the right
        // definition for the field. In an automated run there is no visitor,
        // and Chromium marks EVERY shift as input-caused once touch emulation
        // is on - measured: the same 0.058 shift reports hadRecentInput true
        // at a phone viewport and false at a desktop one. Excluding them there
        // reports 0.000 on a page that visibly jumps, so both are kept and the
        // report says when they disagree.
        window.__perf.clsAll += e.value;
        if (e.hadRecentInput) window.__perf.excluded += 1;
        else window.__perf.cls += e.value;
        // Recorded either way: on a phone viewport every one of these is
        // flagged, and those are the shifts worth naming.
        if (e.value > 0.01 && window.__perf.shifts.length < 6) {
          const src = (e.sources || [])[0];
          const n = src && src.node;
          window.__perf.shifts.push({
            value: +e.value.toFixed(4),
            excluded: !!e.hadRecentInput,
            el: n && n.tagName ? n.tagName.toLowerCase() +
              (n.className && n.className.toString
                ? "." + n.className.toString().trim().split(/\s+/)[0] : "") : "?",
          });
        }
      }
    }).observe({ type: "layout-shift", buffered: true });
  } catch (e) { /* not supported */ }
  try {
    new PerformanceObserver((l) => {
      for (const e of l.getEntries()) {
        window.__perf.longTasks += 1;
        window.__perf.longTaskTime += e.duration;
      }
    }).observe({ type: "longtask", buffered: true });
  } catch (e) { /* not supported */ }
};

/** What the page asks the browser to do before it can paint. */
const BLOCKING = () => {
  const out = { styles: [], scripts: [], fonts: [], images: [] };
  for (const l of document.querySelectorAll("head link[rel=stylesheet]")) {
    const m = l.media;
    if (!m || m === "all" || m === "screen") out.styles.push(l.href);
  }
  for (const s of document.querySelectorAll("head script[src]")) {
    if (!s.async && !s.defer && s.type !== "module") out.scripts.push(s.src);
  }
  for (const sheet of Array.from(document.styleSheets)) {
    let rules = [];
    try { rules = Array.from(sheet.cssRules || []); } catch (e) { continue; }
    for (const r of rules) {
      if (r.constructor && r.constructor.name === "CSSFontFaceRule") {
        out.fonts.push({
          family: (r.style.getPropertyValue("font-family") || "").replace(/["']/g, ""),
          display: r.style.getPropertyValue("font-display") || "",
        });
      }
    }
  }
  for (const img of document.images) {
    const r = img.getBoundingClientRect();
    if (!r.width || !img.naturalWidth) continue;
    out.images.push({
      src: img.currentSrc || img.src,
      natural: img.naturalWidth,
      shown: Math.round(r.width * (window.devicePixelRatio || 1)),
      lazy: img.loading === "lazy",
      aboveFold: r.top < window.innerHeight,
    });
  }
  out.preloads = Array.from(document.querySelectorAll("link[rel=preload]"))
    .map((l) => l.as + ":" + (l.href || "").split("/").pop()).slice(0, 10);
  return out;
};

const TEXT_TYPES = /javascript|json|css|html|xml|svg|plain/i;
const kindOf = (type, url) => {
  if (/javascript|ecmascript/.test(type)) return "script";
  if (/css/.test(type)) return "style";
  if (/font|woff/.test(type) || /\.(woff2?|ttf|otf|eot)(\?|$)/i.test(url)) return "font";
  if (/image|svg/.test(type) || /\.(png|jpe?g|gif|webp|avif|svg|ico)(\?|$)/i.test(url)) return "image";
  if (/video|audio/.test(type)) return "media";
  if (/html/.test(type)) return "document";
  return "other";
};

function findings(data, budgetKb) {
  const f = [];
  const add = (sev, title, detail) => f.push({ sev, title, detail });

  if (data.lcp >= POOR.lcp) {
    add("BLOCKER", "LCP is poor in the lab",
        `${(data.lcp / 1000).toFixed(2)}s against a 2.5s target` +
        (data.lcpEl ? `; the element is ${data.lcpEl}` : ""));
  } else if (data.lcp > GOOD.lcp) {
    add("MAJOR", "LCP is over the target in the lab",
        `${(data.lcp / 1000).toFixed(2)}s against 2.5s` +
        (data.lcpEl ? `; the element is ${data.lcpEl}` : ""));
  }

  // In a lab run nobody clicked anything, so a shift flagged as input-caused
  // is almost certainly a real one. Judge on the total and say so.
  const cls = data.excluded ? (data.clsAll || 0) : data.cls;
  const note = data.excluded
    ? ` (${data.cls.toFixed(3)} after the spec's input exclusion, which the` +
      " touch emulation triggers for every shift; nobody clicked anything in" +
      " this run, so the higher figure is the real one)"
    : "";
  if (cls >= POOR.cls) {
    add("BLOCKER", "The page jumps about while it loads",
        `CLS ${cls.toFixed(3)} against a 0.1 target${note}`);
  } else if (cls > GOOD.cls) {
    add("MAJOR", "Layout shifts past the target",
        `CLS ${cls.toFixed(3)} against 0.1${note}`);
  }
  for (const s of data.shifts || []) {
    if (s.value >= 0.05) {
      add("CHECK", `${s.el} moves the layout by ${s.value}`,
          "Usually an image or embed with no width and height, or a font swap.");
    }
  }

  if (budgetKb && KB(data.totalBytes) > budgetKb) {
    add("MAJOR", "Over the page-weight budget",
        `${KB(data.totalBytes)} KB transferred against a ${budgetKb} KB budget. ` +
        "This budget is the house's, not a published standard - raise it " +
        "deliberately if the page earns it.");
  }

  if (data.thirdPartyBytes > data.firstPartyBytes && data.thirdPartyBytes > 200 * 1024) {
    add("MAJOR", "Third parties weigh more than the site does",
        `${KB(data.thirdPartyBytes)} KB from other hosts against ` +
        `${KB(data.firstPartyBytes)} KB of your own` +
        (data.thirdParties.length ? `; heaviest: ${data.thirdParties[0].host} ` +
          `(${KB(data.thirdParties[0].bytes)} KB)` : "") +
        ". Every one of these is a decision somebody made, and most can go.");
  }

  for (const r of data.uncompressed || []) {
    add("MAJOR", "Served without compression",
        `${r.url.split("/").pop()} is ${KB(r.bytes)} KB and arrives uncompressed. ` +
        "Text compresses by about two thirds; this is free.");
  }

  if ((data.blocking.scripts || []).length) {
    add("MAJOR", `${data.blocking.scripts.length} render-blocking script(s) in the head`,
        data.blocking.scripts.slice(0, 3).map((s) => s.split("/").pop()).join(", ") +
        ". Add `defer`, or move them to the end of the body.");
  }
  if ((data.blocking.styles || []).length > 3) {
    add("CHECK", `${data.blocking.styles.length} stylesheets block the first paint`,
        "Each one is a round trip before anything is drawn.");
  }

  const badFonts = (data.blocking.fonts || []).filter((x) => !x.display);
  if (badFonts.length) {
    add("MAJOR", `${badFonts.length} font face(s) with no font-display`,
        `${badFonts.slice(0, 3).map((x) => x.family).join(", ")}. ` +
        "The text stays invisible while the font downloads; `swap` shows it " +
        "immediately in the fallback.");
  }

  for (const img of data.oversized || []) {
    add("MAJOR", "Image far larger than it is shown at",
        `${img.src.split("/").pop()} is ${img.natural}px wide, displayed at ` +
        `${img.shown}px (${(img.natural / img.shown).toFixed(1)}x)` +
        (img.bytes ? `, ${KB(img.bytes)} KB` : ""));
  }
  for (const img of data.lazyAboveFold || []) {
    add("MAJOR", "Above-the-fold image is lazy-loaded",
        `${img.src.split("/").pop()} is the first thing a visitor sees and the ` +
        "browser has been told to wait before fetching it. That delays LCP " +
        "rather than helping it.");
  }

  if ((data.noCache || []).length) {
    add("CHECK", `${data.noCache.length} static file(s) with no caching`,
        data.noCache.slice(0, 3).map((u) => u.split("/").pop()).join(", ") +
        ". A repeat visitor downloads them again.");
  }

  if (data.longTaskTime > 1000) {
    add("MAJOR", "The main thread is busy for a long time",
        `${Math.round(data.longTaskTime)}ms across ${data.longTasks} long task(s). ` +
        "The page looks loaded and does not respond.");
  }
  return f;
}

async function measure(url, opts) {
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch();
  const width = opts.width;
  const ctx = await browser.newContext({
    viewport: { width, height: width < 768 ? 844 : 900 },
    deviceScaleFactor: width < 768 ? 2 : 1,
    isMobile: width < 768, hasTouch: width < 768,
  });
  const page = await ctx.newPage();
  await page.addInitScript(COLLECT);

  const responses = [];
  page.on("response", async (res) => {
    try {
      const req = res.request();
      const h = res.headers();
      responses.push({
        url: res.url(),
        status: res.status(),
        type: h["content-type"] || "",
        encoding: h["content-encoding"] || "",
        cacheControl: h["cache-control"] || "",
        resourceType: req.resourceType(),
      });
    } catch (e) { /* a redirect or a cancelled request */ }
  });

  const client = await ctx.newCDPSession(page);
  if (opts.throttle) {
    await client.send("Network.enable");
    await client.send("Network.emulateNetworkConditions", {
      offline: false,
      downloadThroughput: THROTTLE.downloadThroughput,
      uploadThroughput: THROTTLE.uploadThroughput,
      latency: THROTTLE.latency,
    });
    await client.send("Emulation.setCPUThrottlingRate", { rate: THROTTLE.cpuRate });
  }
  await client.send("Network.setCacheDisabled", { cacheDisabled: true });

  let status = 0;
  try {
    const r = await page.goto(url, { waitUntil: "load", timeout: 120000 });
    status = r ? r.status() : 0;
  } catch (e) {
    await browser.close();
    return { error: String(e).slice(0, 200) };
  }
  // Let late work land: LCP can still change, and third-party tags usually
  // arrive after load.
  await page.waitForTimeout(3500);

  const perf = await page.evaluate(() => window.__perf || {});
  const blocking = await page.evaluate(BLOCKING);
  // Transfer sizes come from the page's own resource timing; response headers
  // come from the events above. Neither alone has both.
  const timings = await page.evaluate(() => performance
    .getEntriesByType("resource").map((e) => ({
      url: e.name, transfer: e.transferSize, encoded: e.encodedBodySize,
      decoded: e.decodedBodySize, type: e.initiatorType,
    })));
  const navBytes = await page.evaluate(() => {
    const n = performance.getEntriesByType("navigation")[0];
    return n ? { transfer: n.transferSize, encoded: n.encodedBodySize } : null;
  });

  await browser.close();

  const host = new URL(url).hostname.replace(/^www\./, "");
  const byKind = {};
  const byHost = {};
  let total = navBytes ? navBytes.transfer || 0 : 0;
  let first = total, third = 0;
  const uncompressed = [], noCache = [];
  const headerOf = (u) => responses.find((r) => r.url === u) || {};

  for (const t of timings) {
    const bytes = t.transfer || 0;
    total += bytes;
    const h = headerOf(t.url);
    const kind = kindOf(h.type || "", t.url);
    byKind[kind] = (byKind[kind] || 0) + bytes;
    let hostname = "";
    try { hostname = new URL(t.url).hostname.replace(/^www\./, ""); } catch (e) { /* data: */ }
    if (!hostname || hostname === host || hostname.endsWith("." + host)) first += bytes;
    else {
      third += bytes;
      byHost[hostname] = (byHost[hostname] || 0) + bytes;
    }
    if (TEXT_TYPES.test(h.type || "") && !h.encoding && (t.encoded || 0) > 10 * 1024) {
      uncompressed.push({ url: t.url, bytes: t.encoded });
    }
    if (/^(script|style|font|image)$/.test(kind) && h.cacheControl !== undefined) {
      const cc = h.cacheControl || "";
      if (!cc || /no-store|no-cache|max-age=0/.test(cc)) noCache.push(t.url);
    }
  }

  const bytesFor = (src) => {
    const t = timings.find((x) => x.url === src);
    return t ? t.transfer : 0;
  };
  const oversized = (blocking.images || [])
    .filter((i) => i.shown && i.natural / i.shown >= 2 && i.natural > 600)
    .map((i) => ({ ...i, bytes: bytesFor(i.src) }))
    .sort((a, b) => b.bytes - a.bytes).slice(0, 6);
  const lazyAboveFold = (blocking.images || []).filter((i) => i.lazy && i.aboveFold)
    .slice(0, 4);

  return {
    url, status, width, throttled: opts.throttle,
    lcp: perf.lcp || 0, lcpEl: perf.lcpEl || "",
    cls: perf.cls || 0, clsAll: perf.clsAll || 0,
    excluded: perf.excluded || 0, shifts: perf.shifts || [],
    longTasks: perf.longTasks || 0, longTaskTime: perf.longTaskTime || 0,
    requests: timings.length + 1,
    totalBytes: total, firstPartyBytes: first, thirdPartyBytes: third,
    byKind, oversized, lazyAboveFold,
    uncompressed: uncompressed.slice(0, 6),
    noCache: noCache.slice(0, 20),
    thirdParties: Object.entries(byHost).map(([h2, b]) => ({ host: h2, bytes: b }))
      .sort((a, b) => b.bytes - a.bytes).slice(0, 8),
    blocking,
  };
}

function report(d, budgetKb) {
  const L = ["# Load performance", "", `${d.url}`,
             `${d.width}px, cold cache, ` +
             (d.throttled ? "throttled to roughly a mobile connection and a 4x slower CPU"
                          : "**not throttled** - this machine's own speed"), ""];
  L.push("> These are **lab** numbers from one run. Google's thresholds are");
  L.push("> defined on real visitors at the 75th percentile over 28 days, so a");
  L.push("> pass here is not a pass in Search Console. Use this to find the");
  L.push("> fault; use the field data to decide whether the site is fine.");
  L.push("");
  L.push("| | |");
  L.push("|---|---|");
  L.push(`| LCP | ${(d.lcp / 1000).toFixed(2)}s${d.lcpEl ? ` (${d.lcpEl})` : ""} |`);
  L.push(`| CLS | ${(d.excluded ? d.clsAll : d.cls).toFixed(3)}` +
         (d.excluded ? ` (${d.excluded} shift(s) the spec would exclude as ` +
           "input-caused; there was no input)" : "") + " |");
  L.push(`| Main thread blocked | ${Math.round(d.longTaskTime)}ms in ${d.longTasks} long task(s) |`);
  L.push(`| Transferred | ${KB(d.totalBytes)} KB over ${d.requests} requests |`);
  L.push(`| Yours / third party | ${KB(d.firstPartyBytes)} KB / ${KB(d.thirdPartyBytes)} KB |`);
  L.push("");
  const kinds = Object.entries(d.byKind).sort((a, b) => b[1] - a[1]);
  if (kinds.length) {
    L.push("| What | KB |");
    L.push("|---|---|");
    for (const [k, b] of kinds) L.push(`| ${k} | ${KB(b)} |`);
    L.push("");
  }
  if (d.thirdParties.length) {
    L.push("**Third parties:** " +
      d.thirdParties.map((t) => `${t.host} ${KB(t.bytes)} KB`).join(", "));
    L.push("");
  }

  const f = findings(d, budgetKb);
  const bySev = (s) => f.filter((x) => x.sev === s);
  for (const sev of ["BLOCKER", "MAJOR", "CHECK"]) {
    const list = bySev(sev);
    if (!list.length) continue;
    L.push(`## ${sev} (${list.length})`, "");
    for (const x of list) L.push(`- **${x.title}** - ${x.detail}`);
    L.push("");
  }
  if (!f.length) L.push("Nothing found. Read the numbers above anyway.", "");
  return { text: L.join("\n") + "\n", findings: f };
}

async function main() {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) {
    console.error("usage: node perf.js <url> [--out <dir>] [--width 390] " +
                  "[--budget-kb 2048] [--no-throttle]");
    process.exit(2);
  }
  const at = (n, d) => {
    const i = args.indexOf("--" + n);
    return i > -1 && args[i + 1] ? args[i + 1] : d;
  };
  const out = at("out", "perf");
  const width = parseInt(at("width", "390"), 10);
  const budgetKb = parseInt(at("budget-kb", "2048"), 10);
  const throttle = !args.includes("--no-throttle");

  const d = await measure(url, { width, throttle });
  if (d.error) {
    console.error(`could not load ${url}: ${d.error}`);
    process.exit(2);
  }
  fs.mkdirSync(out, { recursive: true });
  const r = report(d, budgetKb);
  fs.writeFileSync(path.join(out, "perf.md"), r.text, "utf8");
  fs.writeFileSync(path.join(out, "perf.json"),
    JSON.stringify({ ...d, findings: r.findings, budgetKb }, null, 1), "utf8");
  console.log(r.text);
  console.log(`written to ${path.join(out, "perf.md")}`);
  const bad = r.findings.filter((x) => x.sev !== "CHECK").length;
  process.exit(bad ? 1 : 0);
}

if (require.main === module) main();
module.exports = { findings, report, kindOf, GOOD, POOR, KB };
