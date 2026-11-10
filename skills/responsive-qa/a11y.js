/**
 * Can everyone actually use this page?
 *
 *   node a11y.js <url> [--routes /,/about] [--out <dir>]
 *                      [--widths 390,1440] [--axe <path to axe.min.js>]
 *
 * Runs axe-core for the WCAG 2 A and AA rules, then adds the checks a rule
 * engine cannot make on its own: whether the skip link goes anywhere, whether
 * the landmark set a screen reader offers is complete, whether the heading
 * outline reads in order, whether anything focusable is hidden from assistive
 * technology while still being reachable, and whether keyboard focus is
 * visible at all.
 *
 * **It runs at more than one width on purpose.** Tap-target size, reflow and
 * the order focus moves in all change on a phone, and a pass taken only at
 * 1440 never opens the width where those fail.
 *
 * What it cannot tell you: whether the page makes sense when read aloud,
 * whether the reading order matches the visual order for a sighted user, or
 * whether a custom widget behaves like the thing it imitates. Roughly half of
 * WCAG needs a person. This finds the half that does not.
 */
const fs = require("fs");
const https = require("https");
const path = require("path");
const { execSync } = require("child_process");

const HERE = __dirname;
const VENDOR = path.join(HERE, "vendor");
const AXE_CDN = "https://cdn.jsdelivr.net/npm/axe-core/axe.min.js";

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

function download(url, dest) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        return download(res.headers.location, dest).then(resolve, reject);
      }
      if (res.statusCode !== 200) return reject(new Error("HTTP " + res.statusCode));
      const out = fs.createWriteStream(dest);
      res.pipe(out);
      out.on("finish", () => out.close(() => resolve(dest)));
    }).on("error", reject);
  });
}

/**
 * Find axe-core, and fetch it once if it is nowhere.
 *
 * The version this project first used lived in a temp folder, which is
 * cleared, so the tool worked until the day it did not and failed with a
 * message about a missing file rather than a missing dependency.
 */
async function findAxe(explicit) {
  if (explicit && fs.existsSync(explicit)) return { path: explicit, from: "given" };
  const vendored = path.join(VENDOR, "axe.min.js");
  if (fs.existsSync(vendored)) return { path: vendored, from: "vendor" };
  try {
    const g = path.join(execSync("npm root -g", { encoding: "utf8" }).trim(),
                        "axe-core", "axe.min.js");
    if (fs.existsSync(g)) return { path: g, from: "npm global" };
  } catch (e) { /* no npm */ }
  fs.mkdirSync(VENDOR, { recursive: true });
  process.stderr.write("axe-core not found locally; fetching it once into " +
                       VENDOR + "\n");
  await download(AXE_CDN, vendored);
  return { path: vendored, from: "downloaded" };
}

/** Everything here is read off the rendered page. */
function srChecks() {
  const notes = [];
  const q = (s) => [...document.querySelectorAll(s)];
  const shown = (e) => e.offsetParent !== null || e.getClientRects().length > 0;

  // A skip link has to exist, point at something real, and come first.
  const firstFocusable = q("a[href], button, input, select, textarea, [tabindex]")
    .filter((e) => e.tabIndex >= 0)[0];
  const skip = q("a[href^='#']").find((a) => /skip|jump/i.test(a.textContent || ""));
  if (!skip) notes.push({ sev: "MAJOR", kind: "skip-link", detail: "no skip link" });
  else {
    const id = skip.getAttribute("href").slice(1);
    if (!document.getElementById(id)) {
      notes.push({ sev: "MAJOR", kind: "skip-link",
                   detail: `points at #${id}, which is not on the page` });
    } else if (firstFocusable !== skip) {
      notes.push({ sev: "CHECK", kind: "skip-link",
                   detail: "exists but is not the first thing focus reaches" });
    }
  }

  // The landmarks a screen reader offers in its rotor.
  const land = {
    banner: q("header, [role=banner]").filter((e) => !e.closest("main")).length,
    navigation: q("nav, [role=navigation]").length,
    main: q("main, [role=main]").length,
    contentinfo: q("footer, [role=contentinfo]").filter((e) => !e.closest("main")).length,
  };
  for (const [name, n] of Object.entries(land)) {
    if (n === 0) notes.push({ sev: "MAJOR", kind: "landmark", detail: `no ${name} landmark` });
    if (name === "main" && n > 1) {
      notes.push({ sev: "MAJOR", kind: "landmark", detail: `${n} main landmarks` });
    }
  }
  const navs = q("nav, [role=navigation]");
  if (navs.length > 1) {
    const unnamed = navs.filter((n) => !n.getAttribute("aria-label") &&
                                       !n.getAttribute("aria-labelledby"));
    if (unnamed.length) {
      notes.push({ sev: "CHECK", kind: "landmark",
                   detail: `${unnamed.length} of ${navs.length} navigation landmarks ` +
                           "have no name, so they all read as \"navigation\"" });
    }
  }

  // The heading outline is how most screen-reader users move around a page.
  const hs = q("h1,h2,h3,h4,h5,h6").filter(shown);
  const levels = hs.map((h) => Number(h.tagName[1]));
  const h1s = levels.filter((l) => l === 1).length;
  if (h1s !== 1) {
    notes.push({ sev: h1s === 0 ? "MAJOR" : "CHECK", kind: "headings",
                 detail: `${h1s} visible h1` });
  }
  for (let i = 1; i < levels.length; i++) {
    if (levels[i] - levels[i - 1] > 1) {
      notes.push({ sev: "CHECK", kind: "headings",
                   detail: `h${levels[i - 1]} jumps to h${levels[i]} at ` +
                           `"${hs[i].textContent.trim().slice(0, 40)}"` });
      break;
    }
  }

  const focusables = q("a[href], button, input, select, textarea, " +
                       "[tabindex]:not([tabindex='-1'])");
  // aria-hidden only matters while the thing can still be reached. `inert`
  // and tabindex="-1" both take it out of the tab order, which is the right
  // way to park a carousel clone or a faded-out CTA.
  const hiddenFocusable = focusables
    .filter((e) => e.closest("[aria-hidden=true]") && !e.closest("[inert]") &&
                   e.tabIndex >= 0)
    .map((e) => e.tagName.toLowerCase() +
                (e.className ? "." + String(e.className).split(" ")[0] : ""));
  if (hiddenFocusable.length) {
    notes.push({ sev: "MAJOR", kind: "aria",
                 detail: `${hiddenFocusable.length} focusable element(s) reachable ` +
                         `inside aria-hidden: ${[...new Set(hiddenFocusable)].slice(0, 3).join(", ")}` });
  }

  const nameOf = (e) => (e.getAttribute("aria-label") ||
    (e.getAttribute("aria-labelledby") &&
      (document.getElementById(e.getAttribute("aria-labelledby")) || {}).textContent) ||
    e.textContent || e.getAttribute("title") || e.getAttribute("alt") ||
    (e.querySelector("img") && e.querySelector("img").alt) || "").trim();
  const unnamed = focusables.filter((e) => shown(e) && !nameOf(e) &&
                                           e.type !== "hidden");
  if (unnamed.length) {
    notes.push({ sev: "MAJOR", kind: "name",
                 detail: `${unnamed.length} focusable element(s) with no accessible ` +
                         `name: ${unnamed.slice(0, 3).map((e) => e.tagName.toLowerCase() +
                           (e.className ? "." + String(e.className).split(" ")[0] : "")).join(", ")}` });
  }
  return { notes, landmarks: land, headings: levels.length, focusables: focusables.length };
}

/**
 * Can you see where you are when tabbing?
 *
 * A stylesheet that sets `outline: none` and puts nothing back is the most
 * common accessibility defect there is, and no rule engine reports it, because
 * the rule only fires on the computed style of a focused element.
 */
async function focusVisible(page) {
  return page.evaluate(async () => {
    const out = { checked: 0, invisible: [], trapped: false };
    const focusables = [...document.querySelectorAll(
      "a[href], button, input:not([type=hidden]), select, textarea, " +
      "[tabindex]:not([tabindex='-1'])")]
      .filter((e) => e.offsetParent !== null || e.getClientRects().length);
    const snap = (e) => {
      const s = getComputedStyle(e);
      return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow,
              s.borderColor, s.backgroundColor, s.textDecorationLine].join("|");
    };
    for (const el of focusables.slice(0, 25)) {
      const before = snap(el);
      el.focus();
      // getComputedStyle is live, so read after focus has actually moved.
      await new Promise((r) => requestAnimationFrame(r));
      const after = snap(el);
      out.checked += 1;
      if (before === after && document.activeElement === el) {
        out.invisible.push(el.tagName.toLowerCase() +
          (el.className ? "." + String(el.className).split(" ")[0] : ""));
      }
    }
    return out;
  });
}

function severityOf(impact) {
  if (impact === "critical" || impact === "serious") return "MAJOR";
  return "CHECK";
}

async function main() {
  const args = process.argv.slice(2);
  const url = args.find((a) => !a.startsWith("--"));
  if (!url) {
    console.error("usage: node a11y.js <url> [--routes /,/about] [--out <dir>] " +
                  "[--widths 390,1440] [--axe <path>]");
    process.exit(2);
  }
  const at = (n, d) => {
    const i = args.indexOf("--" + n);
    return i > -1 && args[i + 1] ? args[i + 1] : d;
  };
  const base = url.replace(/\/$/, "");
  const routes = at("routes", "/").split(",").map((r) => r.trim()).filter(Boolean);
  const widths = at("widths", "390,1440").split(",").map(Number).filter(Boolean);
  const out = at("out", "a11y");
  fs.mkdirSync(out, { recursive: true });

  const axe = await findAxe(at("axe", ""));
  const axeSrc = fs.readFileSync(axe.path, "utf8");
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch();
  const rows = [];

  for (const width of widths) {
    const ctx = await browser.newContext({
      viewport: { width, height: width < 768 ? 844 : 900 },
      deviceScaleFactor: width < 768 ? 2 : 1,
      isMobile: width < 768, hasTouch: width < 768,
    });
    for (const route of routes) {
      const page = await ctx.newPage();
      let status = 0;
      try {
        const r = await page.goto(base + route, { waitUntil: "load", timeout: 90000 });
        status = r ? r.status() : 0;
      } catch (e) {
        rows.push({ width, route, error: String(e).slice(0, 160) });
        await page.close();
        continue;
      }
      // Let anything that mounts on becoming visible mount. A synthetic
      // scroll is ignored by smooth-scroll libraries, so drive a real wheel.
      await page.mouse.move(Math.min(600, width / 2), 400);
      for (let i = 0; i < 10; i++) {
        await page.mouse.wheel(0, 900);
        await page.waitForTimeout(220);
      }
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForTimeout(2500);

      await page.addScriptTag({ content: axeSrc });
      const axeResult = await page.evaluate(async () => await window.axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      }));
      const version = await page.evaluate(() => window.axe.version);
      const sr = await page.evaluate(srChecks);
      const focus = await focusVisible(page);

      const shape = (list) => list.map((v) => ({
        id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length,
        sample: v.nodes.slice(0, 2).map((n) => n.target.join(" ")),
      }));
      rows.push({
        width, route, status, axeVersion: version,
        violations: shape(axeResult.violations),
        // axe cannot read a colour off an image or a gradient, so those land
        // in `incomplete` rather than `violations` - which is exactly where a
        // contrast problem on a hero hides.
        incomplete: shape(axeResult.incomplete),
        sr, focus,
      });
      const v = axeResult.violations.length;
      console.log(`${String(width).padEnd(5)} ${route.padEnd(26)} ${status} ` +
                  `axe=${v} violation type(s), ${axeResult.incomplete.length} to look at, ` +
                  `${sr.notes.length} sr note(s), ${focus.invisible.length} with no focus style`);
      await page.close();
    }
    await ctx.close();
  }
  await browser.close();

  const L = ["# Accessibility", "", base,
             `${routes.length} route(s) at ${widths.join(", ")}px`,
             `axe-core ${(rows.find((r) => r.axeVersion) || {}).axeVersion || "?"} (${axe.from})`, ""];
  L.push("> axe finds roughly a third to a half of WCAG. A clean run here means");
  L.push("> the machine-checkable half is clean; reading order, link text that");
  L.push("> makes sense out of context, and whether a custom widget behaves like");
  L.push("> the thing it imitates still need a person.");
  L.push("");

  let worst = 0;
  for (const kind of ["violations", "sr", "focus"]) {
    for (const r of rows) {
      if (kind === "violations" && (r.violations || []).some(
        (v) => severityOf(v.impact) === "MAJOR")) worst = 1;
      if (kind === "sr" && (r.sr && r.sr.notes || []).some((n) => n.sev === "MAJOR")) worst = 1;
      if (kind === "focus" && r.focus && r.focus.invisible.length) worst = 1;
    }
  }

  for (const r of rows) {
    L.push(`## ${r.route} at ${r.width}px`, "");
    if (r.error) { L.push(`Did not load: ${r.error}`, ""); continue; }
    if (r.violations.length) {
      for (const v of r.violations) {
        L.push(`- **[${v.impact}] ${v.id}** x${v.nodes} - ${v.help}` +
               (v.sample.length ? `  \n  \`${v.sample.join("` `")}\`` : ""));
      }
    } else L.push("- axe: no violations");
    for (const n of (r.sr && r.sr.notes) || []) {
      L.push(`- **[${n.sev}] ${n.kind}** - ${n.detail}`);
    }
    if (r.focus && r.focus.invisible.length) {
      L.push(`- **[MAJOR] focus** - ${r.focus.invisible.length} of ${r.focus.checked} ` +
             "focusable elements show no visible change when focused: " +
             `${[...new Set(r.focus.invisible)].slice(0, 4).join(", ")}. ` +
             "Somebody using a keyboard cannot see where they are.");
    }
    if (r.incomplete.length) {
      L.push("", "Needs a person to look:");
      for (const v of r.incomplete.slice(0, 6)) {
        L.push(`- ${v.id} x${v.nodes} - ${v.help}`);
      }
    }
    L.push("");
  }

  fs.writeFileSync(path.join(out, "a11y.md"), L.join("\n") + "\n", "utf8");
  fs.writeFileSync(path.join(out, "a11y.json"),
    JSON.stringify({ base, routes, widths, axe: axe.from, rows }, null, 1), "utf8");
  console.log(`\nwritten to ${path.join(out, "a11y.md")}`);
  process.exit(worst);
}

if (require.main === module) main();
module.exports = { severityOf, findAxe };
