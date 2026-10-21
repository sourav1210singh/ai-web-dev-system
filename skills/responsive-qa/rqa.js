#!/usr/bin/env node
/**
 * Responsive QA — open a page at real device widths and find the bugs a
 * developer would find by looking, but measured instead of eyeballed.
 *
 *   node rqa.js <url> [--out <dir>] [--widths 360,390,768,1440] [--full]
 *
 * Writes <out>/report.md, <out>/findings.json and a screenshot per width.
 * Exit code 1 if any BLOCKER or MAJOR finding exists, so it can gate a claim.
 */
const fs = require("fs");
const path = require("path");

process.env.PLAYWRIGHT_BROWSERS_PATH =
  process.env.PLAYWRIGHT_BROWSERS_PATH || "C:\\playwright-browsers";

// playwright is installed globally on this machine, which node does not
// resolve by default — fall back to the npm global root.
function loadPlaywright() {
  try { return require("playwright"); } catch (e) { /* keep looking */ }
  const { execSync } = require("child_process");
  const roots = [process.env.NODE_PATH];
  try { roots.push(execSync("npm root -g", { encoding: "utf8" }).trim()); } catch (e) {}
  roots.push(path.join(process.env.APPDATA || "", "npm", "node_modules"));
  for (const r of roots) {
    if (!r) continue;
    const p = path.join(r, "playwright");
    if (fs.existsSync(p)) return require(p);
  }
  console.error("playwright not found. Install it:  npm i -g playwright");
  process.exit(2);
}
const { chromium } = loadPlaywright();

const DEFAULT_WIDTHS = [360, 390, 768, 1024, 1440, 1920];
const HEIGHTS = { 360: 640, 390: 844, 768: 1024, 1024: 768, 1440: 900, 1920: 1080 };

function arg(name, fallback) {
  const i = process.argv.indexOf("--" + name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

// ---------------------------------------------------------------- in-page audit
/* eslint-disable no-undef */
function auditInPage(isMobile) {
  const out = [];
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const add = (sev, kind, msg, el, extra) =>
    out.push({
      sev, kind, msg,
      el: el ? describe(el) : null,
      ...(extra || {}),
    });

  function describe(el) {
    if (!el || !el.tagName) return null;
    const id = el.id ? "#" + el.id : "";
    const cls = (el.className && typeof el.className === "string")
      ? "." + el.className.trim().split(/\s+/).slice(0, 2).join(".")
      : "";
    const txt = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40);
    return (el.tagName.toLowerCase() + id + cls + (txt ? ` "${txt}"` : "")).slice(0, 110);
  }

  function visible(el) {
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || +s.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }

  // 1. horizontal overflow — the single most common responsive bug
  const docW = document.documentElement.scrollWidth;
  if (docW > vw + 1) {
    add("BLOCKER", "overflow-x",
        `Page scrolls sideways: content is ${docW}px wide in a ${vw}px viewport (+${docW - vw}px).`);
    const seen = new Set();
    for (const el of document.querySelectorAll("body *")) {
      if (!visible(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 || r.left < -1) {
        // only report the outermost offender in each branch
        let p = el.parentElement, covered = false;
        while (p && p !== document.body) {
          if (seen.has(p)) { covered = true; break; }
          p = p.parentElement;
        }
        if (covered) continue;
        seen.add(el);
        add("MAJOR", "overflow-x-element",
            `Sticks out to x=${Math.round(r.right)}px (viewport ${vw}px).`, el,
            { overhang: Math.round(r.right - vw) });
        if (seen.size >= 8) break;
      }
    }
  }

  // an element hidden only for screen readers is meant to be 1px — not a bug
  function srOnly(el) {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const c = (p.className && typeof p.className === "string") ? p.className : "";
      if (/screen-reader|sr-only|visually-hidden|visuallyhidden|skip-link/i.test(c)) return true;
      const s = getComputedStyle(p);
      if (s.clip === "rect(0px, 0px, 0px, 0px)" || s.clipPath === "inset(50%)") return true;
    }
    return false;
  }

  // 2. broken images — only when a real source was given and failed.
  //    An <img> with no src yet is a lazy-load placeholder, not a broken image.
  for (const img of document.images) {
    const src = (img.currentSrc || img.getAttribute("src") || "").trim();
    const lazy = img.loading === "lazy" || img.hasAttribute("data-src") ||
                 img.hasAttribute("data-lazy-src") || img.hasAttribute("srcset") === false && !src;
    if (!src) {
      if (!lazy && visible(img))
        add("MINOR", "img-no-src", "Image element has no src.", img);
      continue;
    }
    if (img.complete && img.naturalWidth === 0) {
      add("BLOCKER", "broken-image", `Image fails to load: ${src.slice(0, 120)}`, img);
    }
  }

  // 3. images with no alt (SEO + accessibility)
  let noAlt = 0;
  for (const img of document.images) {
    if (!img.hasAttribute("alt") && !srOnly(img)) {
      noAlt++;
      const name = (img.currentSrc || img.getAttribute("src") ||
                    img.getAttribute("data-src") || img.getAttribute("data-lazy-src") ||
                    "").split("/").pop() || "(no src yet - lazy loaded)";
      if (noAlt <= 5) add("MAJOR", "img-no-alt", `No alt attribute: ${name}`, img);
    }
  }
  if (noAlt > 5) add("MAJOR", "img-no-alt", `${noAlt} images have no alt attribute in total.`);

  // 4. oversized image payload
  for (const img of document.images) {
    const r = img.getBoundingClientRect();
    if (!r.width || !img.naturalWidth) continue;
    const ratio = img.naturalWidth / (r.width * (window.devicePixelRatio || 1));
    if (ratio > 2.5 && img.naturalWidth > 1000) {
      add("MINOR", "img-oversized",
          `Served at ${img.naturalWidth}px but displayed at ${Math.round(r.width)}px (${ratio.toFixed(1)}x too big).`,
          img);
    }
  }

  if (isMobile) {
    // 5. tap targets
    let small = 0;
    for (const el of document.querySelectorAll("a, button, input, select, textarea, [role=button]")) {
      if (!visible(el) || srOnly(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 44 || r.height < 44) {
        small++;
        if (small <= 6)
          add("MAJOR", "tap-target",
              `Tap target is ${Math.round(r.width)}x${Math.round(r.height)}px, below the 44x44 minimum.`, el);
      }
    }
    if (small > 6) add("MAJOR", "tap-target", `${small} tap targets are under 44x44px in total.`);

    // 6. text too small to read on a phone
    let tiny = 0;
    for (const el of document.querySelectorAll("p, li, span, a, td, label, div")) {
      if (!el.childElementCount && el.textContent.trim().length > 12 && visible(el)) {
        const fs2 = parseFloat(getComputedStyle(el).fontSize);
        if (fs2 && fs2 < 12) {
          tiny++;
          if (tiny <= 5) add("MINOR", "text-too-small", `Font size ${fs2}px is below the 12px readable minimum.`, el);
        }
      }
    }
    if (tiny > 5) add("MINOR", "text-too-small", `${tiny} text nodes render below 12px in total.`);

    // 7. fixed overlays eating the screen
    for (const el of document.querySelectorAll("body *")) {
      const s = getComputedStyle(el);
      if (s.position !== "fixed" || !visible(el)) continue;
      const r = el.getBoundingClientRect();
      const share = (r.width * r.height) / (vw * vh);
      if (share > 0.3 && r.top < vh * 0.9)
        add("MAJOR", "fixed-overlay",
            `A fixed element covers ${Math.round(share * 100)}% of the screen.`, el);
    }
  }

  // 8. hero should fit the first screen (standing rule on PPC landing pages)
  const hero = document.querySelector(
    "header + section, main > section:first-of-type, .hero, [class*=hero], section");
  if (hero && visible(hero)) {
    const h = hero.getBoundingClientRect().height;
    if (h > vh * 1.15)
      add("MINOR", "hero-overflows",
          `First section is ${Math.round(h)}px tall against a ${vh}px screen — the CTA is below the fold.`, hero);
  }

  // 9. elements clipped by an ancestor with hidden overflow
  for (const el of document.querySelectorAll("h1, h2, h3, p, button, a")) {
    if (!visible(el) || srOnly(el)) continue;
    if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== "visible") {
      add("MINOR", "text-clipped",
          `Text is cut off: needs ${el.scrollWidth}px but the box is ${el.clientWidth}px.`, el);
    }
  }

  // ---- scale and proportion: the page is not broken, it just does not use
  //      the screen. This is the "bade desktop pe responsive nahi hai" family.
  const scale = { vw, vh };

  // 11. hero dead space - a top-aligned hero leaves a gap that grows with the
  //     screen. Measured, not guessed: section height vs content height.
  const heroEl = document.querySelector(
    "main > section:first-of-type, header + section, .hero, [class*=hero]");
  if (heroEl && visible(heroEl)) {
    const hr = heroEl.getBoundingClientRect();
    let top = Infinity, bottom = -Infinity;
    for (const ch of heroEl.querySelectorAll("*")) {
      if (!visible(ch) || !ch.textContent.trim()) continue;
      const r = ch.getBoundingClientRect();
      if (r.height && r.height < hr.height) {
        top = Math.min(top, r.top);
        bottom = Math.max(bottom, r.bottom);
      }
    }
    if (isFinite(top)) {
      const content = Math.round(bottom - top);
      const dead = Math.round(hr.height - content);
      scale.hero = { height: Math.round(hr.height), content, dead,
                     align: getComputedStyle(heroEl).alignItems };
      if (dead > 200 && vw >= 1024)
        add("MINOR", "hero-dead-space",
            `Hero is ${Math.round(hr.height)}px tall for ${content}px of content: `
            + `${dead}px of empty space. A top-aligned hero grows this with every `
            + `extra pixel of screen height.`, heroEl);
      if (dead < 24 && vw < 768)
        add("MINOR", "hero-no-breathing-room",
            `Hero content fills the hero exactly (${dead}px slack). The text `
            + `touches both ends of its own section.`, heroEl);
    }
  }

  // 12. the container never grows, so a large monitor shows a narrow strip
  //    The signal is an element with a px max-width that caps the content.
  //    A full-bleed section is NOT the container, so look for the capped one.
  let widest = 0, widestEl = null, cap = 0;
  for (const el of document.querySelectorAll(
      "main *, body > div *, section > div, header > div, footer > div")) {
    if (!visible(el)) continue;
    const s = getComputedStyle(el);
    const mw = parseFloat(s.maxWidth);
    if (!mw || s.maxWidth === "none" || !/px$/.test(s.maxWidth)) continue;
    if (mw >= vw) continue;                 // not capping anything here
    const r = el.getBoundingClientRect();
    if (r.width > widest) { widest = r.width; widestEl = el; cap = mw; }
  }
  scale.contentCap = cap ? Math.round(cap) : null;
  scale.widestContent = Math.round(widest);
  if (vw >= 1600 && widest && widest < vw * 0.78) {
    add("MINOR", "container-never-grows",
        `Content is only ${Math.round(widest)}px wide in a ${vw}px viewport, `
        + `leaving ${Math.round((vw - widest) / 2)}px of empty margin each side. `
        + `The container is centred but never uses the room.`, widestEl);
  }

  // 13. overflow-x:hidden that hides nothing and breaks position:sticky
  for (const el of [document.body, document.documentElement]) {
    const s = getComputedStyle(el);
    if (s.overflowX === "hidden" || s.overflow === "hidden") {
      const sticky = [...document.querySelectorAll("header, nav, [class*=sticky]")]
        .some(x => getComputedStyle(x).position === "sticky");
      scale.bodyOverflowHidden = true;
      add(sticky ? "MAJOR" : "MINOR", "overflow-hidden-on-root",
          `overflow-x:hidden on <${el.tagName.toLowerCase()}>`
          + (docW <= vw + 1 ? ", and nothing actually overflows here" : "")
          + (sticky ? ". In several browsers this silently breaks "
                      + "position:sticky on descendants, and this page has a "
                      + "sticky header." : "."), el);
      break;
    }
  }

  // 14. anchor scrolling overshoots the sticky header
  const sp = parseFloat(getComputedStyle(document.documentElement).scrollPaddingTop);
  const stickyEl = [...document.querySelectorAll("header, nav")]
    .find(x => getComputedStyle(x).position === "sticky" ||
               getComputedStyle(x).position === "fixed");
  if (sp && stickyEl) {
    const hh = Math.round(stickyEl.getBoundingClientRect().height);
    scale.scrollPaddingTop = sp;
    scale.stickyHeaderHeight = hh;
    if (Math.abs(sp - hh) > 12)
      add("MINOR", "anchor-overshoot",
          `scroll-padding-top is ${sp}px but the sticky header measures ${hh}px, `
          + `so in-page anchors land ${Math.round(sp - hh)}px off.`, stickyEl);
  }

  const h1el = document.querySelector("h1");
  if (h1el) scale.h1FontSize = parseFloat(getComputedStyle(h1el).fontSize);

  // 10. heading structure (SEO)
  const h1s = [...document.querySelectorAll("h1")].filter(visible);
  if (h1s.length === 0) add("MAJOR", "seo-no-h1", "The page has no visible H1.");
  if (h1s.length > 1) add("MINOR", "seo-many-h1", `The page has ${h1s.length} H1 elements; it should have one.`);

  return {
    findings: out,
    scale,
    stats: { viewportWidth: vw, viewportHeight: vh, documentWidth: docW,
             images: document.images.length, links: document.links.length },
  };
}
/* eslint-enable no-undef */

// ---------------------------------------------------------------- runner
(async () => {
  const url = process.argv[2];
  if (!url || url.startsWith("--")) {
    console.error("usage: node rqa.js <url> [--out dir] [--widths 360,768,1440] [--full]");
    process.exit(2);
  }
  const outDir = path.resolve(arg("out", "rqa-report"));
  const widths = arg("widths", "").trim()
    ? arg("widths").split(",").map((n) => parseInt(n.trim(), 10)).filter(Boolean)
    : DEFAULT_WIDTHS;
  const fullPage = process.argv.includes("--full");
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const all = [];
  const consoleErrors = [];

  for (const w of widths) {
    const h = HEIGHTS[w] || 900;
    const isMobile = w < 768;
    const ctx = await browser.newContext({
      viewport: { width: w, height: h },
      deviceScaleFactor: isMobile ? 2 : 1,
      isMobile,
      hasTouch: isMobile,
      userAgent: isMobile
        ? "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Mobile Safari/537.36"
        : undefined,
    });
    const page = await ctx.newPage();
    page.on("console", (m) => {
      if (m.type() === "error") consoleErrors.push(`[${w}px] ${m.text().slice(0, 180)}`);
    });
    page.on("pageerror", (e) => consoleErrors.push(`[${w}px] ${String(e).slice(0, 180)}`));

    let status = null;
    try {
      const resp = await page.goto(url, { waitUntil: "networkidle", timeout: 45000 });
      status = resp ? resp.status() : null;
    } catch (e) {
      try { await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 }); }
      catch (e2) {
        all.push({ width: w, error: String(e2).slice(0, 200), findings: [] });
        await ctx.close();
        continue;
      }
    }
    // let lazy content and scroll-triggered work settle
    await page.evaluate(async () => {
      await new Promise((r) => {
        let y = 0;
        const step = () => {
          y += window.innerHeight;
          window.scrollTo(0, y);
          if (y < document.body.scrollHeight && y < 20000) setTimeout(step, 120);
          else { window.scrollTo(0, 0); setTimeout(r, 400); }
        };
        step();
      });
    });
    await page.waitForTimeout(500);

    const res = await page.evaluate(auditInPage, isMobile);
    const shot = path.join(outDir, `${w}px.png`);
    await page.screenshot({ path: shot, fullPage });
    all.push({ width: w, status, screenshot: shot, ...res });
    await ctx.close();
    console.error(`  checked ${w}px — ${res.findings.length} finding(s)`);
  }
  await browser.close();

  // ---- cross-viewport: a heading that is identical at 768 and 1920 is set
  //      at one breakpoint and then never scales again.
  const sizes = all.filter(v => v.scale && v.scale.h1FontSize)
                   .map(v => [v.width, v.scale.h1FontSize]);
  const wide = sizes.filter(([w]) => w >= 768);
  if (wide.length >= 2) {
    const vals = [...new Set(wide.map(([, s2]) => s2))];
    if (vals.length === 1) {
      const target = all.find(v => v.width === wide[wide.length - 1][0]);
      if (target) target.findings.push({
        sev: "MINOR", kind: "heading-not-fluid", el: "h1",
        msg: `h1 is exactly ${vals[0]}px at every width from `
             + `${wide[0][0]}px to ${wide[wide.length - 1][0]}px. One `
             + `breakpoint and then nothing: large but not large enough on a `
             + `monitor, heavy on a tablet. Use clamp().`,
      });
    }
  }

  // ------------------------------------------------------------- report
  const order = { BLOCKER: 0, MAJOR: 1, MINOR: 2 };
  const counts = { BLOCKER: 0, MAJOR: 0, MINOR: 0 };
  for (const v of all) for (const f of v.findings || []) counts[f.sev]++;

  const L = [];
  L.push(`# Responsive QA — ${url}`, "");
  L.push(`Checked ${new Date().toISOString().slice(0, 16).replace("T", " ")} at ` +
         `${widths.map((w) => w + "px").join(", ")}.`, "");
  L.push(`**${counts.BLOCKER} blocker, ${counts.MAJOR} major, ${counts.MINOR} minor**`, "");
  if (counts.BLOCKER + counts.MAJOR === 0) L.push("No blocking or major problem found.", "");

  for (const v of all) {
    L.push(`## ${v.width}px`, "");
    if (v.error) { L.push("Page failed to load: " + v.error, ""); continue; }
    L.push(`- HTTP ${v.status ?? "?"} · document ${v.stats.documentWidth}px in a ` +
           `${v.stats.viewportWidth}px viewport · ${v.stats.images} images`);
    L.push(`- Screenshot: \`${path.basename(v.screenshot)}\``);
    const sc = v.scale || {};
    if (sc.hero)
      L.push(`- Hero: ${sc.hero.height}px tall, ${sc.hero.content}px of `
             + `content, ${sc.hero.dead}px empty (align-items: ${sc.hero.align})`);
    if (sc.widestContent)
      L.push(`- Content container: ${sc.widestContent}px wide`
             + (sc.contentCap ? ` (capped at ${sc.contentCap}px)` : "")
             + ` in a ${sc.vw}px viewport`);
    if (sc.h1FontSize) L.push(`- h1: ${sc.h1FontSize}px`);
    L.push("");
    const fs2 = [...(v.findings || [])].sort((a, b) => order[a.sev] - order[b.sev]);
    if (!fs2.length) { L.push("Nothing found at this width.", ""); continue; }
    L.push("| Severity | What | Where |", "|---|---|---|");
    for (const f of fs2)
      L.push(`| ${f.sev} | ${f.msg.replace(/\|/g, "\\|")} | ${f.el ? "`" + f.el.replace(/\|/g, "\\|") + "`" : "page"} |`);
    L.push("");
  }
  if (consoleErrors.length) {
    L.push("## Console errors", "");
    for (const e of [...new Set(consoleErrors)].slice(0, 15)) L.push("- `" + e + "`");
    L.push("");
  }

  fs.writeFileSync(path.join(outDir, "report.md"), L.join("\n"), "utf8");
  fs.writeFileSync(path.join(outDir, "findings.json"),
                   JSON.stringify({ url, widths, counts, viewports: all, consoleErrors }, null, 1), "utf8");

  console.log(L.join("\n"));
  console.error(`\nreport: ${path.join(outDir, "report.md")}`);
  process.exit(counts.BLOCKER + counts.MAJOR > 0 ? 1 : 0);
})();
