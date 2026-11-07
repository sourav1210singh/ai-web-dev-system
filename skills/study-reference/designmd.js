/**
 * Turn a measured page into a DESIGN.md.
 *
 *   node designmd.js <spec.json> [--out DESIGN.md] [--name "Client"]
 *
 * DESIGN.md is Google Stitch's format for handing a design system to a coding
 * agent: machine-readable tokens at the top, prose underneath saying what the
 * numbers mean. Agents read it and build UI that stays consistent, instead of
 * being told "make it look modern" and inventing a new system per page.
 *
 * study.js already measures everything this needs, so nothing new is read off
 * the page here. This maps those measurements onto the format and names them.
 *
 * What it will not do is invent. Components are described only where they were
 * measured, and everything that was not measured is listed as not measured.
 * A design document that guesses is worse than a short one.
 */
const fs = require("fs");
const path = require("path");

// --- colour helpers ----------------------------------------------------
function rgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function lum(hex) {
  const c = rgb(hex);
  if (!c) return null;
  const [r, g, b] = c.map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}
function sat(hex) {
  const c = rgb(hex);
  if (!c) return 0;
  const max = Math.max(...c), min = Math.min(...c);
  return max === 0 ? 0 : (max - min) / max;
}
/**
 * How much colour there is, independent of how dark it is.
 *
 * Saturation is chroma divided by the brightest channel, so it climbs as a
 * colour gets darker: a near-black navy reads 0.88 and would be picked as the
 * brand colour ahead of the actual brand colour. Absolute chroma separates
 * them - a real accent sits around 0.7, a dark ink around 0.17.
 */
function chroma(hex) {
  const c = rgb(hex);
  if (!c) return 0;
  return (Math.max(...c) - Math.min(...c)) / 255;
}
function contrast(a, b) {
  const la = lum(a), lb = lum(b);
  if (la === null || lb === null) return null;
  return +(((Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)).toFixed(2));
}

// --- the measured lists arrive as [value, count] pairs -----------------
// study.js tallies as [{ value, count }]. A fixture written from memory used
// [value, count] pairs instead, the tests passed on it, and the first real
// spec.json produced a DESIGN.md with every token blank - the shape was never
// checked against a file the tool had actually written.
const vals = (list) => (list || []).map((x) => {
  if (x && typeof x === "object" && !Array.isArray(x)) return x.value;
  return Array.isArray(x) ? x[0] : x;
});
const px = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? Math.round(n) : null;
};

/**
 * The base unit the spacing was built on.
 *
 * Worth stating rather than guessing: a scale on a 4px base and one on an 8px
 * base look identical in a screenshot and produce different components. The
 * answer is whichever unit divides the most measured values.
 */
function baseUnit(numbers) {
  // Largest first, and a tie goes to the larger unit. Everything divisible by
  // 8 is also divisible by 4, so taking the first match that fits returns 4
  // for every 8px system there is - and a component built on the wrong base
  // is half a step out everywhere.
  let best = { unit: 8, hits: -1 };
  for (const unit of [10, 8, 6, 5, 4]) {
    const hits = numbers.filter((n) => n > 0 && n % unit === 0).length;
    if (hits > best.hits) best = { unit, hits };
  }
  const micro = numbers.some((n) => n > 0 && n % best.unit !== 0 && n % 2 === 0);
  return { ...best, micro, coverage: numbers.length ? best.hits / numbers.length : 0 };
}

const SPACING_NAMES = ["xxs", "xs", "sm", "md", "base", "lg", "xl", "xxl", "section"];
const ROUND_NAMES = ["none", "xs", "sm", "md", "lg", "xl"];

/** The roles study.js records, in the names the format uses. */
const ROLE_TOKEN = {
  h1: "display-xl", h2: "display-lg", h3: "display-md", h4: "display-sm",
  h5: "title-md", h6: "title-sm", body: "body-md", button: "button-md",
  link: "link", "nav link": "nav-link",
};

function nameColours(spec) {
  const bgs = vals(spec.background).filter((c) => /^#[0-9a-f]{6}$/i.test(c));
  const fgs = vals(spec.foreground).filter((c) => /^#[0-9a-f]{6}$/i.test(c));
  const out = {};
  if (bgs[0]) out.canvas = bgs[0];
  const surface = bgs.find((c) => c !== out.canvas && chroma(c) < 0.25);
  if (surface) out["surface-soft"] = surface;
  // ink is the darkest text, body is the running text, muted is quieter than
  // both. The most frequent foreground is the body copy, not the headline
  // colour, so naming it "ink" labels every heading with the wrong token.
  const byDark = [...fgs].sort((a, b) => (lum(a) ?? 1) - (lum(b) ?? 1));
  if (byDark[0]) out.ink = byDark[0];
  if (fgs[0] && fgs[0] !== out.ink) out.body = fgs[0];
  const floor = Math.max(lum(out.ink) ?? 0, lum(out.body) ?? 0);
  const muted = byDark.find((c) => c !== out.ink && c !== out.body &&
                                   lum(c) !== null && lum(c) > floor + 0.05);
  if (muted) out.muted = muted;

  // The brand colour is the saturated one. A page is mostly greys and one or
  // two colours that mean something; picking "most frequent" returns a grey.
  const candidates = [...bgs, ...fgs].filter((c) => chroma(c) >= 0.35 &&
    lum(c) !== null && lum(c) > 0.03 && lum(c) < 0.92);
  if (candidates[0]) {
    out.primary = candidates[0];
    const onWhite = contrast(candidates[0], "#ffffff") || 0;
    const onBlack = contrast(candidates[0], "#000000") || 0;
    out["on-primary"] = onWhite >= onBlack ? "#ffffff" : "#000000";
    const second = candidates.find((c) => c !== out.primary);
    if (second) out.accent = second;
  }
  const hairline = vals(spec.borders)
    .map((b) => (String(b).match(/#[0-9a-f]{6}/i) || [])[0]).filter(Boolean)[0];
  if (hairline) out.hairline = hairline;
  return out;
}

function buildTokens(spec) {
  const type = spec.type || {};
  const typography = {};
  for (const [role, t] of Object.entries(type)) {
    const token = ROLE_TOKEN[role] || role.replace(/\s+/g, "-");
    typography[token] = {
      fontFamily: t.family, fontSize: t.size, fontWeight: t.weight,
      lineHeight: t.lineHeight, letterSpacing: t.letterSpacing,
      ...(t.transform && t.transform !== "none" ? { textTransform: t.transform } : {}),
      _sample: t.sample,
    };
  }

  const radii = [...new Set(vals(spec.radii).map(px).filter((n) => n !== null))]
    .sort((a, b) => a - b);
  const rounded = {};
  radii.slice(0, ROUND_NAMES.length).forEach((r, i) => {
    rounded[r >= 9999 ? "full" : ROUND_NAMES[i]] = r + "px";
  });
  if (radii.some((r) => r >= 500)) rounded.full = "9999px";

  const spaceNums = [...new Set([...vals(spec.gaps), ...vals(spec.sectionPadding)]
    .map(px).filter((n) => n !== null && n > 0))].sort((a, b) => a - b);
  const base = baseUnit(spaceNums);
  const spacing = {};
  spaceNums.slice(0, SPACING_NAMES.length).forEach((n, i) => {
    spacing[SPACING_NAMES[i]] = n + "px";
  });

  return { colors: nameColours(spec), typography, rounded, spacing, base,
           spaceNums };
}

function yaml(obj, indent) {
  const pad = " ".repeat(indent);
  return Object.entries(obj).map(([k, v]) => {
    if (v && typeof v === "object") {
      const inner = Object.entries(v).filter(([kk]) => !kk.startsWith("_"))
        .map(([kk, vv]) => `${pad}  ${kk}: ${JSON.stringify(vv)}`).join("\n");
      return `${pad}${k}:\n${inner}`;
    }
    return `${pad}${k}: ${JSON.stringify(v)}`;
  }).join("\n");
}

/**
 * study.js writes `{ url, measured, views: [...], reduced }`, one view per
 * width, not the flat object the builder wants. Taking the first view would
 * describe the page as it is on a phone, where the type scale is compressed
 * and half the layout is stacked, so the widest usable view is the one that
 * describes the design.
 */
function normalise(raw) {
  if (!raw || !Array.isArray(raw.views)) return raw || {};
  const usable = raw.views.filter((v) => v && !v.error && v.tokens);
  if (!usable.length) return { url: raw.url, measuredAt: raw.measured };
  const widthOf = (v) => v.width || (v.tokens && v.tokens.viewport
                                     && v.tokens.viewport.w) || 0;
  const widest = usable.reduce((a, b) => (widthOf(b) > widthOf(a) ? b : a));
  // The measurements live under `tokens`, and motion under `motion`. Spreading
  // the view itself gives you screenshot paths and nothing to build from.
  return {
    ...(widest.tokens || {}),
    ...(widest.motion || {}),
    url: raw.url,
    measuredAt: String(raw.measured || "").slice(0, 10),
    reducedMotion: typeof raw.reduced === "string" ? raw.reduced
      : raw.reduced && (raw.reduced.verdict || raw.reduced.summary),
    widthsStudied: usable.map(widthOf).filter(Boolean),
    describedAt: widthOf(widest),
  };
}

function build(rawSpec, name) {
  const spec = normalise(rawSpec);
  const t = buildTokens(spec);
  const shadows = vals(spec.shadows).filter((s) => s && s !== "none");
  const families = vals(spec.families);
  const containers = vals(spec.container).map(px).filter(Boolean);
  const L = [];

  L.push("---");
  L.push(`version: alpha`);
  L.push(`name: ${name}`);
  L.push(`source: ${spec.url || "unknown"}`);
  L.push(`measured: ${spec.measuredAt || new Date().toISOString().slice(0, 10)}`);
  if (spec.describedAt) {
    L.push(`describes: ${spec.describedAt}px viewport` +
           (spec.widthsStudied && spec.widthsStudied.length > 1
             ? ` (of ${spec.widthsStudied.join(", ")} studied)` : ""));
  }
  L.push("");
  L.push("colors:");
  L.push(yaml(t.colors, 2));
  L.push("");
  L.push("typography:");
  L.push(yaml(t.typography, 2));
  L.push("");
  L.push("rounded:");
  L.push(yaml(t.rounded, 2));
  L.push("");
  L.push("spacing:");
  L.push(yaml(t.spacing, 2));
  L.push("---");
  L.push("");

  L.push(`# ${name}`);
  L.push("");
  L.push("Every value below was measured off the rendered page, not read from a");
  L.push("stylesheet and not guessed. Where something was not measured it says so;");
  L.push("fill those in from the real design rather than inventing them.");
  L.push("");

  L.push("## Typography");
  L.push("");
  L.push(`Families in use: ${families.slice(0, 4).join(", ") || "not measured"}.`);
  if (families.length > 3) {
    L.push("");
    L.push(`**${families.length} families is more than a system needs.** Two is`);
    L.push("usual, three is a lot. Check whether the extras are icon fonts or a");
    L.push("widget's own stylesheet before copying them forward.");
  }
  L.push("");
  L.push("| Token | Size | Weight | Line height | Letter spacing | Seen on |");
  L.push("|---|---|---|---|---|---|");
  for (const [token, v] of Object.entries(t.typography)) {
    L.push(`| \`{typography.${token}}\` | ${v.fontSize} | ${v.fontWeight} | ` +
           `${v.lineHeight} | ${v.letterSpacing} | ${(v._sample || "").slice(0, 32)} |`);
  }
  L.push("");
  const sizes = vals(spec.sizes).map(px).filter(Boolean);
  if (sizes.length > 8) {
    L.push(`**${sizes.length} distinct font sizes were measured.** A system that`);
    L.push("people can hold in their head runs six to eight. More than that is");
    L.push("usually drift rather than design, and it is the clearest tell of a page");
    L.push("assembled section by section.");
    L.push("");
  }
  L.push("**If the brand font is not licensed for this build**, name the substitute");
  L.push("here and say what you adjusted - the closest open-source face plus a");
  L.push("line-height nudge keeps the proportions, and leaving it unsaid means the");
  L.push("next person re-picks a different one.");
  L.push("");

  L.push("## Layout");
  L.push("");
  L.push(`- **Base unit:** ${t.base.unit}px` +
         (t.base.micro ? " (with a 2px micro-step)" : "") +
         ` - it divides ${Math.round(t.base.coverage * 100)}% of the measured values.`);
  if (t.base.coverage < 0.7) {
    L.push(`- **The spacing is not on a consistent scale.** Only ` +
           `${Math.round(t.base.coverage * 100)}% of values sit on it, so treat the ` +
           `tokens above as a starting point and settle the scale before building.`);
  }
  L.push(`- **Measured steps:** ${t.spaceNums.slice(0, 12).join(", ")}px`);
  if (containers.length) {
    L.push(`- **Content width:** ${containers.join(", ")}px measured at the widths studied.`);
  }
  const secPad = vals(spec.sectionPadding).map(px).filter(Boolean);
  if (!secPad.length) {
    // Going quiet here reads as "no finding". It means the page builds its
    // vertical rhythm out of margins and gaps rather than section padding,
    // which is a thing to know before copying the spacing.
    L.push("- **No section padding was measured.** The vertical rhythm is not");
    L.push("  coming from padding on the sections; read it off the gaps above and");
    L.push("  the screenshot before deciding the band spacing.");
  }
  if (secPad.length) {
    const big = Math.max(...secPad);
    L.push(`- **Section padding:** up to ${big}px vertical. For reference, a dense`);
    L.push(`  marketplace runs about 64px and SaaS marketing 80-96px, so this page`);
    L.push(`  is ${big < 56 ? "tighter than" : big > 104 ? "looser than" : "inside"} the usual range.`);
  }
  L.push("");

  L.push("## Elevation");
  L.push("");
  if (!shadows.length) {
    L.push("No shadows were measured. The page gets its depth from surface colour");
    L.push("and spacing, and anything added now will look foreign to it.");
  } else {
    L.push(`${shadows.length} distinct shadow${shadows.length > 1 ? "s" : ""} measured:`);
    L.push("");
    for (const s of shadows.slice(0, 5)) L.push(`- \`${String(s).slice(0, 110)}\``);
    L.push("");
    if (shadows.length > 3) {
      L.push("**More than three tiers is usually drift, not a ladder.** Strong");
      L.push("systems tend to have one shadow and a flat default, with most surfaces");
      L.push("flat. Shadowing every card is the fastest way to make a page read as");
      L.push("generated.");
    } else {
      L.push("Keep the default flat. Depth belongs on the few surfaces that lift");
      L.push("off the page, not on every card.");
    }
  }
  L.push("");

  L.push("## Motion");
  L.push("");
  const trans = vals(spec.transitions), anim = vals(spec.animations);
  if (!trans.length && !anim.length) {
    L.push("Nothing animated was measured. Do not add motion that the reference");
    L.push("does not have; it will not match.");
  } else {
    for (const x of trans.slice(0, 6)) L.push(`- transition: \`${String(x).slice(0, 90)}\``);
    for (const x of anim.slice(0, 4)) L.push(`- animation: \`${String(x).slice(0, 90)}\``);
    if (spec.reducedMotion) {
      L.push("");
      L.push(`- Under \`prefers-reduced-motion\`: ${spec.reducedMotion}`);
    }
  }
  L.push("");

  L.push("## Components");
  L.push("");
  L.push("Only the roles below were measured, and only their type and colour.");
  L.push("Padding, height, border and every state (hover, focus, active, disabled)");
  L.push("were **not measured** and must come from the real design.");
  L.push("");
  for (const [token, v] of Object.entries(t.typography)) {
    if (!/button|nav|link/.test(token)) continue;
    L.push(`- \`${token}\`: ${v.fontSize} / ${v.fontWeight}, ` +
           `${v.fontFamily}`);
  }
  L.push("");
  L.push("**Components reference tokens, never raw values.** Write");
  L.push("`{colors.primary}` and `{spacing.lg}`, not `#ff385c` and `24px`. A");
  L.push("component with a hard-coded hex is the one that gets missed when the");
  L.push("palette changes.");
  L.push("");

  L.push("## Not measured");
  L.push("");
  L.push("- Contrast ratios against their real backgrounds, per pair");
  L.push("- Focus states, error states, disabled states");
  L.push("- Dark mode, if the site has one");
  L.push("- Anything behind a login, a modal or a hover that was never triggered");
  L.push("- Print and email styles");
  L.push("");
  L.push("Fill these in before treating this file as the system rather than a");
  L.push("measurement of one page on one day.");

  return L.join("\n") + "\n";
}

function main() {
  const args = process.argv.slice(2);
  const specPath = args.find((a) => !a.startsWith("--"));
  if (!specPath) {
    console.error('usage: node designmd.js <spec.json> [--out DESIGN.md] [--name "Client"]');
    process.exit(2);
  }
  const at = (f, d) => {
    const i = args.indexOf("--" + f);
    return i > -1 && args[i + 1] ? args[i + 1] : d;
  };
  let spec;
  try {
    spec = JSON.parse(fs.readFileSync(specPath, "utf8"));
  } catch (e) {
    console.error(`could not read ${specPath}: ${e.message}`);
    process.exit(2);
  }
  const name = at("name", spec.name ||
    (spec.url ? String(spec.url).replace(/^https?:\/\//, "").split("/")[0] : "Reference"));
  const out = at("out", path.join(path.dirname(specPath), "DESIGN.md"));
  fs.writeFileSync(out, build(spec, name), "utf8");
  console.log(`DESIGN.md written: ${out}`);
  console.log("Read it before handing it to anything. It records what was");
  console.log("measured; the parts it says were not measured are still yours.");
}

if (require.main === module) main();
module.exports = { build, buildTokens, baseUnit, nameColours, normalise,
                   contrast, chroma, sat, lum };
