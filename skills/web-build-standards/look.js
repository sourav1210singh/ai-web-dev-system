#!/usr/bin/env node
/**
 * look.js - judge a page we built against this house's look rules.
 *
 *   node look.js <spec.json>            judge a study already taken
 *   node look.js <spec.json> --json     machine readable
 *
 * The rules this checks are not invented here. Every finding quotes the line
 * in web-build-standards it comes from, because a design opinion with no rule
 * behind it is an argument and a rule with no measurement behind it is a
 * suggestion. Both were true until now: sections 1 and 3 state the numbers
 * (six to eight font sizes, one shadow tier, 16-24px reveal travel) and
 * nothing ever counted them on our own output. study.js measures all of it
 * already, for a reference. This points the same measurement at us.
 *
 * Input is the spec.json study.js writes:
 *   { url, measured, views: [ { width, status, tokens, motion, hover,
 *                               reveal, headerAfter } ], reduced }
 * Tallies inside tokens are [{ value, count }]. Read off a real file rather
 * than assumed: a generator built on a remembered shape once produced a
 * document with every token blank.
 *
 * The widest view is judged, for the same reason designmd.js describes it:
 * a phone view has a compressed scale and describes the breakpoint.
 */
"use strict";
const fs = require("fs");

const RULES = {
  reveal: "section 1: a static page reads as AI-made. Section reveal on " +
          "scroll, fade plus 16-24px rise, 500-700ms",
  hover: "section 1: hover on anything clickable, a lift of 4-8px or a " +
         "scale of 1.02-1.03, 150-250ms",
  sizes: "section 3: six to eight font sizes, not fourteen",
  shadow: "section 3: flat by default, one shadow tier, not a ladder",
  base: "section 3: state the base unit and stay on it, 4px with a 2px " +
        "micro-step, or 8px",
  loud: "section 3: display weights stay modest, and there is one loud moment",
  gradient: "section 3: no startup gradient purple-to-blue washes",
  rhythm: "section 3: section padding runs about 64px dense, 80-96px marketing",
};

function px(v) {
  const m = /^(-?[\d.]+)px$/.exec(String(v || "").trim());
  return m ? parseFloat(m[1]) : null;
}

function hues(str) {
  // Every rgb/rgba triple in a gradient, as a hue in degrees. Enough to tell
  // a purple-to-blue wash from a photograph scrim.
  const out = [];
  const re = /rgba?\(\s*(\d+)[,\s]+(\d+)[,\s]+(\d+)/g;
  let m;
  while ((m = re.exec(str))) {
    const [r, g, b] = [+m[1] / 255, +m[2] / 255, +m[3] / 255];
    const max = Math.max(r, g, b), min = Math.min(r, g, b), d = max - min;
    if (d < 0.08) continue;                       // grey, carries no hue
    let h;
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h = Math.round(h * 60);
    out.push(h < 0 ? h + 360 : h);
  }
  return out;
}

function judge(view) {
  const t = view.tokens || {};
  const find = [];
  const add = (level, rule, what, detail) =>
    find.push({ level, rule: RULES[rule], what, detail });

  // ---- section 1: the page must not feel flat ------------------------
  const rev = view.reveal || {};
  if ((rev.checked || 0) > 0 && !(rev.count > 0)) {
    add("MAJOR", "reveal", "nothing reveals on scroll",
        `${rev.checked} elements entered the viewport and none of them moved`);
  } else if (rev.count > 0) {
    const travel = rev.medianTravel;
    if (typeof travel === "number" && (travel < 12 || travel > 40)) {
      add("MINOR", "reveal", "reveal travel is outside the house range",
          `median ${travel}px against 16 to 24px`);
    }
    const secs = parseFloat(String((rev.typicalDuration || [])[0] || ""));
    if (!isNaN(secs) && (secs < 0.35 || secs > 0.9)) {
      add("MINOR", "reveal", "reveal duration is outside the house range",
          `${secs}s against 0.5 to 0.7s`);
    }
  }

  const hover = Array.isArray(view.hover) ? view.hover : [];
  if (!hover.length) {
    add("MAJOR", "hover", "nothing responds to hover",
        "no clickable element changed on hover at this width");
  }

  // ---- section 3: the structural tells --------------------------------
  const sizes = (t.sizes || []).map((s) => px(s.value)).filter((n) => n !== null);
  const distinct = new Set(sizes);
  // Fluid type computes to fractional pixels at any given viewport, so a page
  // obeying section 2 (headings must be fluid) looks like scale drift to
  // section 3 (six to eight sizes) if the computed values are counted flat.
  // Measured on three real sites: two use clamp and show 10 values where the
  // design has far fewer roles. Say which it is rather than pick a side.
  const fractional = [...distinct].filter((n) => Math.abs(n - Math.round(n)) > 0.01);
  if (distinct.size > 8) {
    const fluid = fractional.length >= 3;
    add(fluid ? "MINOR" : "MAJOR", "sizes",
        fluid ? "many font sizes, and the page uses fluid type"
              : "too many font sizes in play",
        `${distinct.size} distinct sizes` +
        (fluid ? `, ${fractional.length} of them fractional, which is what ` +
                 `clamp() looks like at one width. Count the roles in ` +
                 `tokens.type, not the computed values: ` : ": ") +
        [...distinct].sort((a, b) => b - a).join(", "));
  }

  const shadows = (t.shadows || []).filter((s) => s.value && s.value !== "none");
  if (shadows.length > 1) {
    const carried = shadows.reduce((n, s) => n + (s.count || 0), 0);
    add("MAJOR", "shadow", "more than one shadow tier",
        `${shadows.length} definitions across ${carried} elements`);
  }

  const spacing = [...(t.gaps || []), ...(t.sectionPadding || [])]
    .map((g) => px(g.value)).filter((n) => n !== null && n > 0);
  if (spacing.length >= 4) {
    const off = spacing.filter((n) => n % 4 !== 0);
    const share = off.length / spacing.length;
    if (share > 0.25) {
      add("MAJOR", "base", "spacing is not on a base unit",
          `${off.length} of ${spacing.length} values are not multiples of 4: ` +
          `${[...new Set(off)].slice(0, 6).join(", ")}`);
    }
  }

  if (distinct.size) {
    const big = Math.max(...distinct);
    const competing = [...distinct].filter((n) => n >= big * 0.6);
    if (competing.length > 2) {
      add("MINOR", "loud", "no single loud moment",
          `${competing.length} sizes compete at the top: ` +
          `${competing.sort((a, b) => b - a).join(", ")}`);
    }
  }

  for (const g of t.gradients || []) {
    const h = hues(g.value || "");
    // Every stop in the blue to violet band, and at least one truly violet.
    // The second half is the discriminator: a navy to sky brand gradient sits
    // entirely under 230 and is not the tell, while the startup wash reaches
    // into the 250s. Measured: rgb(124,58,237) is 262 and rgb(37,99,235) is
    // 221, so a band starting at 230 misses the blue end of the very thing it
    // is looking for.
    if (h.length >= 2 && h.every((x) => x >= 205 && x <= 300) &&
        h.some((x) => x >= 250)) {
      add("MAJOR", "gradient", "a purple to blue wash",
          `hues ${h.join(", ")} in ${String(g.value).slice(0, 60)}`);
      break;
    }
  }

  const pads = (t.sectionPadding || []).map((s) => px(s.value))
    .filter((n) => n !== null && n > 0);
  if (pads.length) {
    const dominant = pads.sort((a, b) => b - a)[0];
    if (dominant < 48 || dominant > 140) {
      add("MINOR", "rhythm", "section rhythm is outside the normal range",
          `largest section padding ${dominant}px against 64 to 96px`);
    }
  }
  return find;
}

function main() {
  const args = process.argv.slice(2);
  const file = args.find((a) => !a.startsWith("--"));
  if (!file) {
    console.log(require("fs").readFileSync(__filename, "utf8")
      .split("*/")[0].replace(/^\/\*\*?/, "").replace(/^ \* ?/gm, ""));
    process.exit(2);
  }
  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (e) {
    console.error(`could not read ${file}: ${e.message}`);
    process.exit(2);
  }
  const views = (spec.views || []).filter((v) => v && v.tokens);
  if (!views.length) {
    console.error("no measured view in that spec. Run study.js first.");
    process.exit(2);
  }
  const view = views.reduce((a, b) => (b.width > a.width ? b : a));
  const findings = judge(view);

  if (args.includes("--json")) {
    console.log(JSON.stringify({ url: spec.url, width: view.width, findings },
                               null, 2));
  } else {
    console.log(`# Look check - ${spec.url || file}`);
    console.log(`judged at ${view.width}px, the widest view measured\n`);
    if (!findings.length) {
      console.log("Nothing against the house rules at this width.");
      console.log("That is not the same as good. It means nothing measured " +
                  "here is wrong, and a person still has to look at it.");
    }
    for (const f of findings) {
      console.log(`  ${f.level.padEnd(7)} ${f.what}`);
      console.log(`          ${f.detail}`);
      console.log(`          rule: ${f.rule}`);
    }
    const major = findings.filter((f) => f.level === "MAJOR").length;
    if (findings.length) {
      console.log(`\n${findings.length} finding(s), ${major} major.`);
    }
  }
  process.exit(findings.some((f) => f.level === "MAJOR") ? 1 : 0);
}

if (require.main === module) main();
module.exports = { judge, hues, px };
