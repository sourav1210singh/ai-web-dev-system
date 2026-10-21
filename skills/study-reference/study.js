#!/usr/bin/env node
/**
 * Study a reference page and write down what it is actually made of, so the
 * rebuild works from measurements instead of from an impression.
 *
 *   node study.js <url> [--out <dir>] [--widths 390,1440] [--full]
 *
 * Writes <out>/spec.md, <out>/spec.json and a screenshot per width.
 * Measures: type scale, colour palette, spacing, radii, shadows, container
 * width, section rhythm, every transition and animation with its duration and
 * easing, what happens on hover, what animates in on scroll and how far it
 * travels, whether the header changes on scroll, and whether any of it is
 * switched off for prefers-reduced-motion.
 *
 * Use it only on a reference you are entitled to use. It records a spec; it
 * does not copy code, markup or assets.
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

const DEFAULT_WIDTHS = [390, 1440];
const HEIGHTS = { 360: 640, 390: 844, 768: 1024, 1024: 768, 1440: 900, 1920: 1080 };

function arg(name, fallback) {
  const i = process.argv.indexOf("--" + name);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

// ------------------------------------------------------------ in-page: tokens
/* eslint-disable no-undef */
function readTokens() {
  const tally = (map, k) => { if (k) map[k] = (map[k] || 0) + 1; };
  const sorted = (map, n) => Object.entries(map)
    .sort((a, b) => b[1] - a[1]).slice(0, n)
    .map(([value, count]) => ({ value, count }));

  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };

  // Modern stylesheets compute to lab() and oklab(), which nobody can rebuild
  // from. Let the browser resolve any colour to plain rgb by painting it.
  const cvs = document.createElement("canvas");
  cvs.width = cvs.height = 1;
  const cx = cvs.getContext("2d", { willReadFrequently: true });
  const hex = (c) => {
    if (!c || c === "none") return c;
    try {
      cx.clearRect(0, 0, 1, 1);
      cx.fillStyle = "#000000";
      cx.fillStyle = c;
      cx.clearRect(0, 0, 1, 1);
      cx.fillRect(0, 0, 1, 1);
      const d = cx.getImageData(0, 0, 1, 1).data;
      const a = +(d[3] / 255).toFixed(2);
      if (a === 0) return "transparent";
      const h = "#" + [d[0], d[1], d[2]]
        .map((n) => n.toString(16).padStart(2, "0")).join("");
      return a < 1 ? h + " @ " + a : h;
    } catch (e) { return c; }
  };
  // the hover probe runs later in this same page and reuses it
  window.__hex = hex;

  const type = {};      // role -> { size, weight, lineHeight, family, ... }
  const sizes = {}, families = {}, weights = {}, radii = {}, shadows = {};
  const fg = {}, bg = {}, borders = {}, gradients = {};
  const gaps = {}, sectionPad = {};
  const roleOf = (el) => {
    const t = el.tagName.toLowerCase();
    if (/^h[1-6]$/.test(t)) return t;
    if (t === "button") return "button";
    if (t === "a") return el.closest("nav") ? "nav link" : "link";
    if (t === "p" || t === "li" || t === "span") return "body";
    return null;
  };

  const all = Array.from(document.querySelectorAll("body *"));
  for (const el of all) {
    if (!visible(el)) continue;
    const cs = getComputedStyle(el);
    const text = (el.textContent || "").trim();

    if (text && el.children.length === 0) {
      tally(sizes, cs.fontSize);
      tally(families, cs.fontFamily.split(",")[0].replace(/["']/g, "").trim());
      tally(weights, cs.fontWeight);
      tally(fg, hex(cs.color));
    }
    // a heading is still a heading when it wraps a span, which is how most
    // real sites write them - reading only leaf text loses every h1
    const role = roleOf(el);
    if (role && text && !type[role]) {
      type[role] = {
        family: cs.fontFamily.split(",")[0].replace(/["']/g, "").trim(),
        size: cs.fontSize, weight: cs.fontWeight,
        lineHeight: cs.lineHeight, letterSpacing: cs.letterSpacing,
        transform: cs.textTransform, color: hex(cs.color),
        sample: text.slice(0, 60),
      };
    }
    if (cs.backgroundColor && cs.backgroundColor !== "rgba(0, 0, 0, 0)") {
      tally(bg, hex(cs.backgroundColor));
    }
    if (/gradient/.test(cs.backgroundImage)) {
      tally(gradients, cs.backgroundImage.slice(0, 120));
    }
    if (cs.borderTopWidth !== "0px") {
      tally(borders, cs.borderTopWidth + " " + cs.borderTopStyle + " " +
        hex(cs.borderTopColor));
    }
    if (cs.borderRadius && cs.borderRadius !== "0px") tally(radii, cs.borderRadius);
    if (cs.boxShadow && cs.boxShadow !== "none") tally(shadows, cs.boxShadow);
    if (/flex|grid/.test(cs.display) && cs.gap && cs.gap !== "normal") {
      tally(gaps, cs.gap);
    }
  }

  // section rhythm: the first ancestor whose own children are the sections.
  // Real sites wrap everything in two or three layout divs, so taking the
  // children of <main> blindly finds one child and reports nothing.
  const tallKids = (el) => Array.from(el.children)
    .filter((k) => visible(k) && k.getBoundingClientRect().height > 80);
  let candidates = Array.from(document.querySelectorAll("section"))
    .filter((el) => visible(el) && el.getBoundingClientRect().height > 80);
  if (candidates.length < 3) {
    // no real <section> markup: walk down past the layout wrappers
    let host = document.querySelector("main") || document.body;
    for (let depth = 0; depth < 5; depth++) {
      const kids = tallKids(host);
      if (kids.length >= 3 || kids.length !== 1) break;
      host = kids[0];
    }
    candidates = tallKids(host);
  }
  const sections = candidates
    .map((el, i) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      tally(sectionPad, cs.paddingTop);
      tally(sectionPad, cs.paddingBottom);
      const heads = el.querySelectorAll("h1,h2,h3");
      return {
        i: i + 1,
        tag: el.tagName.toLowerCase(),
        height: Math.round(r.height),
        vhRatio: +(r.height / window.innerHeight).toFixed(2),
        padTop: cs.paddingTop, padBottom: cs.paddingBottom,
        background: hex(cs.backgroundColor),
        heading: heads[0] ? (heads[0].textContent || "").trim().slice(0, 70) : "",
        columns: getComputedStyle(el).gridTemplateColumns !== "none"
          ? getComputedStyle(el).gridTemplateColumns
          : null,
      };
    });

  // container: the widest repeated content width that is narrower than the
  // viewport is almost always the container
  const widths = {};
  for (const el of all) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.width > window.innerWidth * 0.5 && r.width < window.innerWidth - 8) {
      tally(widths, Math.round(r.width) + "px");
    }
  }

  const fonts = [];
  try {
    document.fonts.forEach((f) => {
      if (f.status === "loaded") fonts.push(f.family + " " + f.weight + " " + f.style);
    });
  } catch (e) { /* not available */ }

  const imgs = Array.from(document.images).filter(visible).map((im) => ({
    ratio: im.naturalWidth && im.naturalHeight
      ? +(im.naturalWidth / im.naturalHeight).toFixed(2) : null,
    ext: (im.currentSrc || im.src || "").split("?")[0].split(".").pop().slice(0, 5),
    srcset: !!im.srcset,
    lazy: im.loading === "lazy",
  }));

  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    documentHeight: document.documentElement.scrollHeight,
    type, fonts: Array.from(new Set(fonts)).slice(0, 12),
    sizes: sorted(sizes, 10), families: sorted(families, 6),
    weights: sorted(weights, 6),
    foreground: sorted(fg, 8), background: sorted(bg, 10),
    borders: sorted(borders, 5), gradients: sorted(gradients, 4),
    radii: sorted(radii, 6), shadows: sorted(shadows, 5),
    gaps: sorted(gaps, 8), sectionPadding: sorted(sectionPad, 8),
    container: sorted(widths, 4),
    sections,
    images: { count: imgs.length, withSrcset: imgs.filter((i) => i.srcset).length,
      lazy: imgs.filter((i) => i.lazy).length,
      formats: Array.from(new Set(imgs.map((i) => i.ext))).slice(0, 6),
      ratios: Array.from(new Set(imgs.map((i) => i.ratio))).filter(Boolean).slice(0, 8) },
  };
}

// ------------------------------------------------------------ in-page: motion
function readMotion() {
  const tally = (map, k) => { if (k) map[k] = (map[k] || 0) + 1; };
  const sorted = (map, n) => Object.entries(map)
    .sort((a, b) => b[1] - a[1]).slice(0, n)
    .map(([value, count]) => ({ value, count }));

  const transitions = {}, animations = {};
  // element counts, not distinct-combination counts. Comparing a reduced
  // motion run against a normal one needs a number that cannot move just
  // because the page rendered slightly differently.
  let movingEls = 0, animatedEls = 0;
  const nonZero = (d) => d && d.split(",").some((x) => parseFloat(x) > 0);
  for (const el of Array.from(document.querySelectorAll("body *"))) {
    const cs = getComputedStyle(el);
    if (nonZero(cs.transitionDuration)) {
      movingEls++;
      tally(transitions, [cs.transitionProperty, cs.transitionDuration,
        cs.transitionTimingFunction, cs.transitionDelay].join(" | "));
    }
    if (cs.animationName && cs.animationName !== "none" &&
        nonZero(cs.animationDuration)) {
      animatedEls++;
      tally(animations, [cs.animationName, cs.animationDuration,
        cs.animationTimingFunction, cs.animationIterationCount,
        cs.animationDelay].join(" | "));
    }
  }

  // keyframes, read off the stylesheets we are allowed to read
  const keyframes = [];
  for (const sheet of Array.from(document.styleSheets)) {
    let rules = null;
    try { rules = sheet.cssRules; } catch (e) { continue; }   // cross-origin
    for (const rule of Array.from(rules || [])) {
      if (rule.type === CSSRule.KEYFRAMES_RULE) {
        keyframes.push({
          name: rule.name,
          steps: Array.from(rule.cssRules).map((k) => k.keyText + " { " +
            (k.style.cssText || "").slice(0, 160) + " }"),
        });
      }
    }
  }

  const sticky = Array.from(document.querySelectorAll("body *"))
    .filter((el) => /fixed|sticky/.test(getComputedStyle(el).position))
    .slice(0, 6)
    .map((el) => ({
      tag: el.tagName.toLowerCase(),
      position: getComputedStyle(el).position,
      height: Math.round(el.getBoundingClientRect().height),
      background: getComputedStyle(el).backgroundColor,
      backdrop: getComputedStyle(el).backdropFilter,
    }));

  return {
    movingEls, animatedEls,
    transitions: sorted(transitions, 12),
    animations: sorted(animations, 10),
    keyframes: keyframes.slice(0, 10),
    sticky,
    scrollBehavior: getComputedStyle(document.documentElement).scrollBehavior,
  };
}

// ---------------------------------------------------- in-page: reveal probing
function markBelowFold() {
  window.__probe = Array.from(document.querySelectorAll("body *"))
    .filter((el) => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return r.top > window.innerHeight * 0.9 && r.width > 40 && r.height > 20 &&
        cs.display !== "none";
    })
    .slice(0, 400);
  return window.__probe.map((el) => {
    const cs = getComputedStyle(el);
    return { o: cs.opacity, t: cs.transform, c: cs.clipPath, v: cs.visibility };
  });
}

function readProbe() {
  return (window.__probe || []).map((el) => {
    const cs = getComputedStyle(el);
    return {
      o: cs.opacity, t: cs.transform, c: cs.clipPath, v: cs.visibility,
      dur: cs.transitionDuration, ease: cs.transitionTimingFunction,
      delay: cs.transitionDelay,
      adur: cs.animationDuration, aname: cs.animationName,
      tag: el.tagName.toLowerCase(),
    };
  });
}

function readHover() {
  const out = [];
  const targets = Array.from(document.querySelectorAll(
    "button, a.btn, a[class*=button], [class*=card], nav a"))
    .slice(0, 8);
  const hx = window.__hex || ((c) => c);
  for (const el of targets) {
    const cs = getComputedStyle(el);
    out.push({
      tag: el.tagName.toLowerCase(),
      label: (el.textContent || "").trim().slice(0, 30),
      before: {
        bg: hx(cs.backgroundColor), color: hx(cs.color),
        transform: cs.transform, shadow: cs.boxShadow,
        border: hx(cs.borderColor), opacity: cs.opacity,
      },
      dur: cs.transitionDuration, ease: cs.transitionTimingFunction,
    });
  }
  window.__hover = targets;
  return out;
}
/* eslint-enable no-undef */

// ------------------------------------------------------------------- analysing
function travelOf(transform) {
  // "matrix(1, 0, 0, 1, 0, 40)" -> 40px of movement
  const m = /matrix\(([^)]+)\)/.exec(transform || "");
  if (!m) return 0;
  const p = m[1].split(",").map((n) => parseFloat(n.trim()));
  if (p.length < 6) return 0;
  return Math.round(Math.max(Math.abs(p[4]), Math.abs(p[5])));
}

function revealSummary(before, after) {
  const revealed = [];
  for (let i = 0; i < Math.min(before.length, after.length); i++) {
    const b = before[i], a = after[i];
    const fadedIn = parseFloat(b.o) < 0.95 && parseFloat(a.o) >= 0.95;
    const moved = b.t !== a.t && b.t !== "none";
    const unclipped = b.c !== a.c && b.c && b.c !== "none";
    if (fadedIn || moved || unclipped) {
      revealed.push({
        tag: a.tag,
        from: { opacity: b.o, transform: b.t, clip: b.c },
        travel: travelOf(b.t),
        duration: a.dur !== "0s" ? a.dur : a.adur,
        easing: a.ease, delay: a.delay, animation: a.aname,
      });
    }
  }
  const dur = {}, ease = {}, travel = [];
  for (const r of revealed) {
    if (r.duration) dur[r.duration] = (dur[r.duration] || 0) + 1;
    if (r.easing) ease[r.easing] = (ease[r.easing] || 0) + 1;
    if (r.travel) travel.push(r.travel);
  }
  travel.sort((a, b) => a - b);
  return {
    count: revealed.length,
    checked: before.length,
    typicalDuration: Object.entries(dur).sort((a, b) => b[1] - a[1])[0] || null,
    typicalEasing: Object.entries(ease).sort((a, b) => b[1] - a[1])[0] || null,
    medianTravel: travel.length ? travel[Math.floor(travel.length / 2)] : 0,
    examples: revealed.slice(0, 8),
  };
}

async function scrollThrough(page) {
  await page.evaluate(async () => {
    const step = Math.round(window.innerHeight * 0.7);
    const end = document.documentElement.scrollHeight;
    for (let y = 0; y < end; y += step) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 320));
    }
    window.scrollTo(0, end);
    await new Promise((r) => setTimeout(r, 900));
  });
}

async function studyWidth(ctx, url, w, outDir, fullPage) {
  const page = await ctx.newPage();
  await page.setViewportSize({ width: w, height: HEIGHTS[w] || 900 });
  let status = null;
  try {
    const r = await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
    status = r ? r.status() : null;
  } catch (e) {
    try {
      const r = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
      status = r ? r.status() : null;
    } catch (e2) {
      await page.close();
      return { width: w, error: String(e2.message || e2) };
    }
  }
  await page.waitForTimeout(1200);

  const before = await page.evaluate(markBelowFold);
  const tokens = await page.evaluate(readTokens);
  const motion = await page.evaluate(readMotion);
  const hoverBefore = await page.evaluate(readHover);

  // what changes when you actually hover
  const hover = [];
  for (let i = 0; i < hoverBefore.length; i++) {
    try {
      await page.evaluate((n) => window.__hover[n].dispatchEvent(
        new MouseEvent("mouseover", { bubbles: true })), i);
      const el = await page.evaluateHandle((n) => window.__hover[n], i);
      await el.asElement().hover({ timeout: 2000 });
      await page.waitForTimeout(420);
      const after = await page.evaluate((n) => {
        const cs = getComputedStyle(window.__hover[n]);
        const hx = window.__hex || ((c) => c);
        return { bg: hx(cs.backgroundColor), color: hx(cs.color),
          transform: cs.transform, shadow: cs.boxShadow,
          border: hx(cs.borderColor), opacity: cs.opacity };
      }, i);
      const b = hoverBefore[i];
      const changed = Object.keys(after).filter((k) => after[k] !== b.before[k]);
      if (changed.length) {
        hover.push({ el: b.tag + " \"" + b.label + "\"", duration: b.dur,
          easing: b.ease,
          changes: changed.map((k) => k + ": " + b.before[k] + " -> " + after[k]) });
      }
    } catch (e) { /* element went away or is not hoverable */ }
  }

  await scrollThrough(page);
  const after = await page.evaluate(readProbe);
  const reveal = revealSummary(before, after);

  const headerAfter = await page.evaluate(() => {
    const h = document.querySelector("header") ||
      Array.from(document.querySelectorAll("body *")).find(
        (el) => /fixed|sticky/.test(getComputedStyle(el).position));
    if (!h) return null;
    const cs = getComputedStyle(h);
    return { height: Math.round(h.getBoundingClientRect().height),
      background: cs.backgroundColor, shadow: cs.boxShadow,
      backdrop: cs.backdropFilter };
  });

  // back to the top before the screenshot. The scroll probe leaves the page
  // at the footer, and a footer is no use as a design reference.
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(700);
  const shotScrollY = await page.evaluate(() => Math.round(window.scrollY));
  const shot = path.join(outDir, `study-${w}.png`);
  await page.screenshot({ path: shot, fullPage });
  await page.close();
  return { width: w, status, tokens, motion, hover, reveal, headerAfter,
    screenshot: shot, shotScrollY };
}

// -------------------------------------------------------------------- report
function list(items, label) {
  if (!items || !items.length) return [`- ${label}: none found`];
  return [`- ${label}: ` + items.map((i) => `\`${i.value}\` (${i.count})`).join(", ")];
}

function buildReport(url, views, reduced) {
  const L = [];
  L.push(`# Reference spec`, ``, `- URL: ${url}`,
    `- Measured: ${new Date().toISOString()}`,
    `- Widths: ${views.map((v) => v.width).join(", ")}`, ``,
    `Measured from the rendered result. It is a spec to build to, not code to`,
    `copy — use it only on a reference you are entitled to use, and never`,
    `reuse its images, fonts or markup.`, ``, `---`, ``);

  for (const v of views) {
    if (v.error) { L.push(`## ${v.width}px`, ``, `Could not load: ${v.error}`, ``); continue; }
    const t = v.tokens, m = v.motion;
    L.push(`## ${v.width}px  (HTTP ${v.status})`, ``);
    L.push(`### Type`, ``);
    for (const [role, d] of Object.entries(t.type)) {
      L.push(`- **${role}** — ${d.family} ${d.size}/${d.lineHeight}, weight ${d.weight}` +
        `, tracking ${d.letterSpacing}` +
        (d.transform !== "none" ? `, ${d.transform}` : "") +
        `, ${d.color}`);
    }
    L.push(``, ...list(t.sizes, "Sizes in use"), ...list(t.families, "Families"),
      ...list(t.weights, "Weights"));
    if (t.fonts.length) L.push(`- Loaded webfonts: ${t.fonts.join("; ")}`);
    L.push(``, `### Colour`, ``, ...list(t.background, "Backgrounds"),
      ...list(t.foreground, "Text"), ...list(t.borders, "Borders"),
      ...list(t.gradients, "Gradients"));
    L.push(``, `### Shape and depth`, ``, ...list(t.radii, "Radii"),
      ...list(t.shadows, "Shadows"));
    L.push(``, `### Space`, ``, ...list(t.sectionPadding, "Section padding"),
      ...list(t.gaps, "Flex and grid gaps"), ...list(t.container, "Content width"));
    L.push(``, `### Rhythm`, ``,
      `Document height ${t.documentHeight}px over ${t.sections.length} sections.`, ``,
      `| # | tag | height | x viewport | padding | heading |`,
      `|---|---|---|---|---|---|`);
    for (const s of t.sections.slice(0, 14)) {
      L.push(`| ${s.i} | ${s.tag} | ${s.height}px | ${s.vhRatio} | ${s.padTop}/${s.padBottom} | ${s.heading || "-"} |`);
    }
    const wrappers = t.sections.filter((s) => s.vhRatio > 4).length;
    if (wrappers >= Math.max(1, t.sections.length / 2)) {
      L.push(``, `**Do not trust this table.** ${wrappers} of ${t.sections.length} ` +
        `rows are taller than four screens, which means this page has no ` +
        `section markup and what was measured is layout wrappers. Read the ` +
        `rhythm off the screenshot instead, and take the section padding from ` +
        `the Space figures above.`);
    }
    L.push(``, `### Motion`, ``);
    L.push(`**Transitions** (property | duration | easing | delay)`, ``);
    for (const x of m.transitions.slice(0, 8)) L.push(`- \`${x.value}\` x${x.count}`);
    if (!m.transitions.length) L.push(`- none`);
    L.push(``, `**Animations** (name | duration | easing | iterations | delay)`, ``);
    for (const x of m.animations.slice(0, 8)) L.push(`- \`${x.value}\` x${x.count}`);
    if (!m.animations.length) L.push(`- none`);
    if (m.keyframes.length) {
      L.push(``, `**Keyframes**`, ``);
      for (const k of m.keyframes) {
        L.push(`- \`@keyframes ${k.name}\``);
        for (const s of k.steps.slice(0, 4)) L.push(`  - ${s}`);
      }
    }
    L.push(``, `**On scroll**`, ``,
      `${v.reveal.count} of ${v.reveal.checked} elements below the fold animate in.`);
    if (v.reveal.typicalDuration) {
      L.push(`Typical duration ${v.reveal.typicalDuration[0]} ` +
        `(${v.reveal.typicalDuration[1]} elements), easing ` +
        `${v.reveal.typicalEasing ? v.reveal.typicalEasing[0] : "?"}, ` +
        `median travel ${v.reveal.medianTravel}px.`);
    }
    for (const e of v.reveal.examples) {
      L.push(`- ${e.tag}: from opacity ${e.from.opacity}` +
        (e.travel ? `, ${e.travel}px away` : "") +
        `, over ${e.duration} ${e.easing}` +
        (e.delay && e.delay !== "0s" ? `, delay ${e.delay}` : ""));
    }
    L.push(``, `**On hover**`, ``);
    if (!v.hover.length) L.push(`- nothing measurable changed on hover`);
    for (const h of v.hover) {
      L.push(`- ${h.el} over ${h.duration} ${h.easing}`);
      for (const c of h.changes) L.push(`  - ${c}`);
    }
    if (m.sticky.length) {
      L.push(``, `**Fixed and sticky**`, ``);
      for (const s of m.sticky) {
        L.push(`- ${s.tag} ${s.position}, ${s.height}px, ${s.background}` +
          (s.backdrop && s.backdrop !== "none" ? `, backdrop ${s.backdrop}` : ""));
      }
      if (v.headerAfter) {
        L.push(`- after scrolling: ${v.headerAfter.height}px, ` +
          `${v.headerAfter.background}, shadow ${v.headerAfter.shadow}`);
      }
    }
    L.push(``, `Scroll behaviour: \`${m.scrollBehavior}\``);
    L.push(``, `### Images`, ``,
      `${t.images.count} images, ${t.images.withSrcset} with srcset, ` +
      `${t.images.lazy} lazy. Formats: ${t.images.formats.join(", ") || "-"}. ` +
      `Aspect ratios: ${t.images.ratios.join(", ") || "-"}.`);
    L.push(``, `Screenshot: \`${path.basename(v.screenshot)}\``, ``, `---`, ``);
  }

  L.push(`## Reduced motion`, ``);
  const base = views.filter((v) => !v.error).pop();
  if (!reduced) {
    L.push(`Not measured.`, ``);
  } else if (reduced.error || !base) {
    L.push(`Could not measure: ${reduced.error || "no usable baseline"}`, ``);
  } else {
    const nb = base.motion.movingEls + base.motion.animatedEls;
    const nr = reduced.motion.movingEls + reduced.motion.animatedEls;
    const drop = nb ? 1 - nr / nb : 0;
    L.push(`Elements with a non-zero transition or animation: ` +
      `**${nb} normally, ${nr} with \`prefers-reduced-motion: reduce\`**` +
      (nb ? ` (${Math.round(drop * 100)}% fewer)` : "") + `.`,
      `Elements animating in on scroll: ${base.reveal.count} normally, ` +
      `${reduced.reveal.count} under reduce.`, ``);
    if (nb === 0) {
      L.push(`There is no motion to switch off.`, ``);
    } else if (drop >= 0.7 ||
               (reduced.reveal.count === 0 && base.reveal.count >= 5)) {
      // one reveal disappearing is noise between two page loads, not proof
      L.push(`This reference respects reduced motion. Match that.`, ``);
    } else if (drop >= 0.2) {
      L.push(`This reference switches off **some** of its motion under ` +
        `reduce. Do better: cover all of it.`, ``);
    } else {
      L.push(`Nothing measurable is switched off under \`reduce\`. If you ` +
        `rebuild this motion, add the media query yourself: wrap it in ` +
        `\`@media (prefers-reduced-motion: no-preference)\`, or disable it ` +
        `under \`reduce\`.`, ``);
    }
  }

  L.push(`## Before you build from this`, ``,
    `1. Look at the screenshots. The numbers describe the page; they do not`,
    `   show you whether it reads well.`,
    `2. Round the measurements to a scale of your own. 23px of padding in a`,
    `   reference is 24px in a system.`,
    `3. Fonts are licensed separately. Check before using the same family.`,
    `4. Rebuild and then measure your own build the same way, so the`,
    `   comparison is numbers against numbers.`, ``);
  return L.join("\n");
}

// ----------------------------------------------------------------------- main
(async () => {
  const url = process.argv[2];
  if (!url || url.startsWith("--")) {
    console.error("usage: node study.js <url> [--out dir] [--widths 390,1440] [--full]");
    process.exit(2);
  }
  const outDir = arg("out", path.join(process.cwd(), "reference-study"));
  const widths = arg("widths", "").split(",").map((n) => parseInt(n.trim(), 10))
    .filter(Boolean);
  const useWidths = widths.length ? widths : DEFAULT_WIDTHS;
  const fullPage = process.argv.includes("--full");
  fs.mkdirSync(outDir, { recursive: true });

  const browser = await chromium.launch();
  const views = [];
  try {
    const ctx = await browser.newContext({ deviceScaleFactor: 1 });
    for (const w of useWidths) {
      process.stderr.write(`studying at ${w}px...\n`);
      views.push(await studyWidth(ctx, url, w, outDir, fullPage));
    }
    await ctx.close();

    // the same page again, with reduced motion asked for
    process.stderr.write("checking prefers-reduced-motion...\n");
    let reduced = null;
    try {
      const rctx = await browser.newContext({ reducedMotion: "reduce" });
      const w = useWidths[useWidths.length - 1];
      const r = await studyWidth(rctx, url, w, path.join(outDir, "reduced"),
        false);
      reduced = r.error ? { error: r.error }
        : { motion: r.motion, reveal: r.reveal };
      await rctx.close();
    } catch (e) {
      reduced = { error: String(e.message || e) };
    }

    const report = buildReport(url, views, reduced);
    fs.writeFileSync(path.join(outDir, "spec.md"), report + "\n", "utf8");
    fs.writeFileSync(path.join(outDir, "spec.json"),
      JSON.stringify({ url, measured: new Date().toISOString(), views, reduced },
        null, 1), "utf8");
    console.log(report);
    console.log(`\nwritten to ${outDir}`);
    const usable = views.filter((v) => !v.error).length;
    process.exit(usable ? 0 : 1);
  } finally {
    await browser.close();
  }
})();
