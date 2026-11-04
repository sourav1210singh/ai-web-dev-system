/**
 * Cross-browser pass: the same pages in Chromium, Firefox and WebKit.
 *
 *   node crossbrowser.js <baseUrl> [--routes /,/about] [--out <dir>]
 *                        [--widths 390,768,1440,1920,2560]
 *
 * rqa.js runs Chromium only, so a page it calls clean has been seen by one
 * engine out of three. This opens each route in all three at every width and
 * records what each one actually did, then reports only the differences that
 * survive measurement.
 *
 * It judges layout quality nowhere - that is rqa.js. What it answers is the
 * narrower question: does this page behave the same in all three engines?
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
  console.error("playwright not found. It is installed globally here, and a bare\n" +
                "require() does not resolve a global module - that is what the\n" +
                "fallback above is for.");
  process.exit(2);
}

const DEFAULT_WIDTHS = [390, 768, 1440, 1920, 2560];
const HEIGHTS = { 360: 640, 390: 844, 768: 1024, 1024: 768, 1440: 900,
                  1920: 1080, 2560: 1440 };

// Noise that is the host's, not the site's. Firefox logs this on every page of
// a Cloudflare-fronted preview host, and reporting it as a site error sends
// somebody hunting for a bug that is not theirs.
const IGNORE_CONSOLE = [
  /__cf_bm.*rejected for invalid domain/i,
  /Partitioned cookie or storage access/i,
];

function arg(name, fallback) {
  const i = process.argv.indexOf("--" + name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

/** Runs in the page. Everything here is read off the rendered DOM. */
function measure() {
  const de = document.documentElement;
  const over = [];
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right > de.clientWidth + 1 || r.left < -1) {
      over.push({
        tag: el.tagName.toLowerCase(),
        cls: (el.className && el.className.toString().slice(0, 60)) || "",
        right: Math.round(r.right),
      });
      if (over.length >= 3) break;
    }
  }
  const h1 = document.querySelector("h1");
  const css = h1 ? getComputedStyle(h1) : null;
  const logo = document.querySelector("header img, img");
  const broken = [...document.images].filter(
    (i) => i.complete && i.naturalWidth === 0 && i.getAttribute("src")).length;
  return {
    scrollWidth: de.scrollWidth,
    clientWidth: de.clientWidth,
    overflows: de.scrollWidth > de.clientWidth + 1,
    overflowBy: Math.max(0, de.scrollWidth - de.clientWidth),
    offenders: over,
    h1: h1 ? {
      size: Math.round(parseFloat(css.fontSize)),
      weight: css.fontWeight,
      family: css.fontFamily.split(",")[0].replace(/["']/g, ""),
      width: Math.round(h1.getBoundingClientRect().width),
    } : null,
    logo: logo ? { src: (logo.currentSrc || logo.src || "").split("/").pop(),
                   width: Math.round(logo.getBoundingClientRect().width) } : null,
    brokenImages: broken,
    bodyBg: getComputedStyle(document.body).backgroundColor,
  };
}

/**
 * Only differences that survive measurement.
 *
 * A screenshot at reduced scale once made one engine look as though it had
 * dropped a bold run; measuring gave the same weight, family and width in all
 * three. So the comparison is on numbers, never on the pictures.
 */
function differences(rows) {
  const out = [];
  const key = (r) => `${r.route} @${r.width}`;
  const groups = {};
  for (const r of rows) (groups[key(r)] = groups[key(r)] || []).push(r);
  for (const [where, group] of Object.entries(groups)) {
    if (group.length < 2) continue;
    const check = {
      "HTTP status": (r) => r.status,
      "overflows the viewport": (r) => r.overflows,
      "h1 size": (r) => r.h1 && r.h1.size,
      "h1 weight": (r) => r.h1 && r.h1.weight,
      "h1 font": (r) => r.h1 && r.h1.family,
      "logo file chosen": (r) => r.logo && r.logo.src,
      "broken images": (r) => r.brokenImages,
      "body background": (r) => r.bodyBg,
    };
    for (const [what, read] of Object.entries(check)) {
      const seen = group.map((r) => [r.engine, JSON.stringify(read(r))]);
      const values = new Set(seen.map(([, v]) => v));
      if (values.size > 1) {
        out.push({ where, what,
                   by: seen.map(([e, v]) => `${e}=${v}`).join("  ") });
      }
    }
  }
  return out;
}

(async () => {
  const { chromium, firefox, webkit } = loadPlaywright();
  const base = (process.argv[2] || "").replace(/\/$/, "");
  if (!base || base.startsWith("--")) {
    console.error("usage: node crossbrowser.js <baseUrl> [--routes /,/about] " +
                  "[--out <dir>] [--widths 390,1440,2560]");
    process.exit(2);
  }
  const routes = arg("routes", "/").split(",").map((r) => r.trim()).filter(Boolean);
  const widths = arg("widths", "").split(",").map(Number).filter(Boolean);
  const WIDTHS = widths.length ? widths : DEFAULT_WIDTHS;
  const OUT = arg("out", "crossbrowser");
  fs.mkdirSync(OUT, { recursive: true });

  const rows = [];
  for (const [name, launcher] of
       [["chromium", chromium], ["firefox", firefox], ["webkit", webkit]]) {
    let browser;
    try {
      browser = await launcher.launch();
    } catch (e) {
      rows.push({ engine: name, error: String(e).slice(0, 200) });
      console.log(`${name}: could not launch - ${String(e).slice(0, 120)}`);
      continue;
    }
    for (const width of WIDTHS) {
      const ctx = await browser.newContext({
        viewport: { width, height: HEIGHTS[width] || 900 }, deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      for (const route of routes) {
        const errors = [];
        page.on("console", (m) => {
          if (m.type() !== "error") return;
          const text = m.text().slice(0, 160);
          if (!IGNORE_CONSOLE.some((rx) => rx.test(text))) errors.push(text);
        });
        page.on("pageerror", (e) => errors.push("PAGEERROR " + String(e).slice(0, 160)));
        let status = 0;
        try {
          const resp = await page.goto(base + route, { waitUntil: "load", timeout: 60000 });
          status = resp ? resp.status() : 0;
          // Let anything that mounts on becoming visible actually mount. A
          // synthetic scroll is ignored by smooth-scroll libraries, so drive a
          // real wheel event.
          await page.mouse.move(Math.min(700, width / 2), 400);
          for (let i = 0; i < 8; i++) {
            await page.mouse.wheel(0, 900);
            await page.waitForTimeout(200);
          }
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.waitForTimeout(1200);
        } catch (e) {
          rows.push({ engine: name, width, route, error: String(e).slice(0, 160) });
          console.log(`${name} ${width} ${route}: FAILED - ${String(e).slice(0, 90)}`);
          continue;
        }
        const m = await page.evaluate(measure);
        const file = `${route.replace(/[^\w]+/g, "-").replace(/^-|-$/g, "") || "home"}-${width}-${name}.png`;
        await page.screenshot({ path: path.join(OUT, file) });
        rows.push({ engine: name, width, route, status, ...m,
                    consoleErrors: errors.slice(0, 4), screenshot: file });
        console.log(`${name.padEnd(9)} ${String(width).padEnd(5)} ${route.padEnd(24)} ` +
                    `${status} overflow=${m.overflows ? m.overflowBy + "px" : "no"} ` +
                    `h1=${m.h1 ? m.h1.size : "-"} errs=${errors.length}`);
      }
      await ctx.close();
    }
    await browser.close();
  }

  const diffs = differences(rows.filter((r) => !r.error));
  const failed = rows.filter((r) => r.error);
  const lines = ["# Cross-browser pass", "", `${base}`,
                 `${routes.length} route(s) x ${WIDTHS.length} width(s) x 3 engines`, ""];
  if (failed.length) {
    lines.push("## Did not load", "");
    for (const f of failed) lines.push(`- ${f.engine} ${f.width || ""} ${f.route || ""}: ${f.error}`);
    lines.push("");
  }
  lines.push("## Differences between engines", "");
  if (!diffs.length) {
    lines.push("None. Every measured value matched across all three engines.");
  } else {
    for (const d of diffs) lines.push(`- **${d.where}** - ${d.what}: ${d.by}`);
  }
  lines.push("", "## Console errors", "");
  const noisy = rows.filter((r) => (r.consoleErrors || []).length);
  if (!noisy.length) lines.push("None.");
  for (const r of noisy) {
    lines.push(`- ${r.engine} ${r.width} ${r.route}`);
    for (const e of r.consoleErrors) lines.push(`  - ${e}`);
  }
  lines.push("", "Screenshots are beside this file. Open them; the numbers above",
             "say what differs, the pictures say whether it matters.");
  fs.writeFileSync(path.join(OUT, "report.md"), lines.join("\n") + "\n");
  fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(
    { base, routes, widths: WIDTHS, differences: diffs, rows }, null, 1));

  console.log(`\n${diffs.length} difference(s) between engines, ` +
              `${failed.length} load failure(s) -> ${path.join(OUT, "report.md")}`);
  process.exit(diffs.length || failed.length ? 1 : 0);
})();
