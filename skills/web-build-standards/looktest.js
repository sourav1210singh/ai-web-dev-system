#!/usr/bin/env node
/**
 * Does look.js catch a flat, AI-looking page, and leave a good one alone?
 *
 * The findings it makes are only worth anything if both halves hold. A check
 * that flags every page is ignored inside a week, and one that flags none was
 * never a check. So every rule below is pinned twice: once on a page that
 * breaks it and once on a page that does not.
 *
 * Fixtures are in the shape study.js actually writes, read off a real
 * spec.json rather than remembered:
 *   { url, views: [ { width, status, tokens, motion, hover, reveal } ] }
 * with every tally as [{ value, count }]. A generator built here once on a
 * remembered shape produced a document with every token blank.
 */
"use strict";
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");
const { judge, hues, px } = require("./look.js");

const RESULTS = [];
const LOOK = path.join(__dirname, "look.js");

function ok(name, cond, extra) {
  RESULTS.push(!!cond);
  console.log(`${cond ? "PASS " : "FAIL "} ${name}` +
              (extra ? `  [${String(extra).slice(0, 110)}]` : ""));
}

const tally = (...vals) => vals.map((v) => ({ value: v, count: 1 }));

/** A page that breaks nothing. Everything else starts from this. */
function good(over) {
  const view = {
    width: 1440,
    status: 200,
    tokens: {
      sizes: tally("64px", "32px", "24px", "18px", "16px", "14px"),
      shadows: tally("rgba(0,0,0,0.08) 0px 1px 2px 0px"),
      radii: tally("8px"),
      gaps: tally("8px", "16px", "24px", "32px"),
      sectionPadding: tally("96px", "64px", "80px"),
      gradients: tally("linear-gradient(rgba(0,0,0,0.45) 0%, rgba(0,0,0,0) 60%)"),
      type: { h1: { size: "64px" } },
    },
    motion: { movingEls: 40, animatedEls: 6, transitions: [] },
    hover: [{ el: 'a "Work"', duration: "0.2s", easing: "ease",
              changes: ["transform: none -> translateY(-6px)"] }],
    reveal: { count: 8, checked: 30, typicalDuration: ["0.6s", 8],
              typicalEasing: ["cubic-bezier(0.16, 1, 0.3, 1)", 8],
              medianTravel: 20, examples: [] },
  };
  Object.assign(view, over || {});
  if (over && over.tokens) {
    view.tokens = Object.assign({}, good().views[0].tokens, over.tokens);
  }
  return { url: "https://example.test/", views: [view] };
}

const has = (find, bit) => find.some((f) => f.what.includes(bit));
const level = (find, bit) =>
  (find.find((f) => f.what.includes(bit)) || {}).level;

function main() {
  // ---------------------------------------------- the page that is fine
  let f = judge(good().views[0]);
  ok("a page that breaks nothing produces no findings", f.length === 0,
     f.map((x) => x.what).join("; "));

  // ------------------------------------------------- section 1: flatness
  f = judge(good({ reveal: { count: 0, checked: 40 } }).views[0]);
  ok("a page where nothing reveals on scroll is a major",
     level(f, "nothing reveals") === "MAJOR", f.map((x) => x.what).join("; "));
  ok("and the finding quotes the rule it came from",
     (f[0] || {}).rule && f[0].rule.includes("section 1"), (f[0] || {}).rule);

  f = judge(good({ reveal: { count: 5, checked: 30, medianTravel: 60,
                             typicalDuration: ["0.6s", 5] } }).views[0]);
  ok("reveal travel far outside the house range is reported",
     has(f, "reveal travel"), f.map((x) => x.what).join("; "));
  f = judge(good({ reveal: { count: 5, checked: 30, medianTravel: 20,
                             typicalDuration: ["2s", 5] } }).views[0]);
  ok("a reveal that runs too long is reported", has(f, "reveal duration"),
     f.map((x) => x.what).join("; "));
  f = judge(good({ reveal: { count: 5, checked: 30, medianTravel: 20,
                             typicalDuration: ["0.6s", 5] } }).views[0]);
  ok("a reveal inside the range is left alone", f.length === 0,
     f.map((x) => x.what).join("; "));

  f = judge(good({ hover: [] }).views[0]);
  ok("a page where nothing responds to hover is a major",
     level(f, "nothing responds to hover") === "MAJOR");

  // --------------------------------------- section 3: structural tells
  f = judge(good({ tokens: { sizes: tally("60px", "48px", "40px", "32px",
    "28px", "24px", "20px", "18px", "16px", "14px") } }).views[0]);
  ok("ten whole-pixel sizes is scale drift, and major",
     level(f, "too many font sizes") === "MAJOR",
     f.map((x) => x.what).join("; "));

  f = judge(good({ tokens: { sizes: tally("54px", "41.04px", "24.208px",
    "19px", "17px", "15px", "14.5px", "14px", "13px", "12px") } }).views[0]);
  ok("the same count with fractional sizes reads as fluid type, not drift",
     level(f, "fluid type") === "MINOR", f.map((x) => x.what).join("; "));
  ok("and it says to count the roles instead",
     (f[0] || {}).detail && f[0].detail.includes("tokens.type"),
     (f[0] || {}).detail);

  f = judge(good({ tokens: { sizes: tally("64px", "32px", "16px") } }).views[0]);
  ok("a short scale raises nothing", f.length === 0);

  f = judge(good({ tokens: { shadows: tally("a 0 1px", "b 0 4px",
                                            "c 0 12px") } }).views[0]);
  ok("a ladder of shadows is a major",
     level(f, "shadow tier") === "MAJOR");
  f = judge(good({ tokens: { shadows: [] } }).views[0]);
  ok("no shadow at all is not a finding, flat is the default",
     f.length === 0, f.map((x) => x.what).join("; "));

  f = judge(good({ tokens: { gaps: tally("3px", "7px", "11px", "13px"),
                             sectionPadding: tally("64px") } }).views[0]);
  ok("spacing off any base unit is a major",
     level(f, "base unit") === "MAJOR", f.map((x) => x.what).join("; "));
  f = judge(good({ tokens: { gaps: tally("8px", "16px", "24px", "48px"),
                             sectionPadding: tally("64px", "96px") } }).views[0]);
  ok("spacing on a 4px base raises nothing", f.length === 0,
     f.map((x) => x.what).join("; "));

  f = judge(good({ tokens: { sizes: tally("64px", "60px", "56px", "16px") } })
            .views[0]);
  ok("several sizes competing at the top means no loud moment",
     has(f, "loud moment"), f.map((x) => x.what).join("; "));

  f = judge(good({ tokens: { gradients: tally(
    "linear-gradient(rgb(124,58,237) 0%, rgb(37,99,235) 100%)") } }).views[0]);
  ok("a purple to blue wash is caught by hue, not by name",
     level(f, "purple to blue") === "MAJOR",
     f.map((x) => x.what).join("; "));
  f = judge(good({ tokens: { gradients: tally(
    "linear-gradient(rgba(0,0,0,0.6) 0%, rgba(0,0,0,0) 70%)") } }).views[0]);
  ok("a photograph scrim is not a startup gradient", f.length === 0,
     f.map((x) => x.what).join("; "));
  f = judge(good({ tokens: { gradients: tally(
    "linear-gradient(rgb(212,178,116) 0%, rgb(180,140,90) 100%)") } }).views[0]);
  ok("a warm brand gradient is not one either", f.length === 0,
     f.map((x) => x.what).join("; "));
  // The discriminator, pinned on its own: a blue brand gradient that never
  // reaches violet is a blue brand gradient. Without this the fix for the
  // blue end of the startup wash would have swallowed it.
  f = judge(good({ tokens: { gradients: tally(
    "linear-gradient(rgb(12,74,160) 0%, rgb(56,160,220) 100%)") } }).views[0]);
  ok("a navy to sky brand gradient is left alone", f.length === 0,
     f.map((x) => x.what).join("; ") +
     " hues " + hues("rgb(12,74,160) rgb(56,160,220)").join(","));

  f = judge(good({ tokens: { sectionPadding: tally("240px", "200px") } })
            .views[0]);
  ok("a section rhythm far outside the range is reported",
     has(f, "section rhythm"), f.map((x) => x.what).join("; "));

  // ------------------------------------------------------------ helpers
  ok("hue reading ignores greys",
     hues("linear-gradient(rgb(10,10,10), rgb(240,240,240))").length === 0);
  ok("hue reading finds a violet", hues("rgb(124,58,237)")[0] > 230);
  ok("px parses a pixel value and rejects anything else",
     px("24px") === 24 && px("2rem") === null && px("") === null);

  // ------------------------------------------------- the widest view wins
  const twoViews = good();
  twoViews.views.push(Object.assign({}, twoViews.views[0], {
    width: 390, tokens: Object.assign({}, twoViews.views[0].tokens,
                                      { shadows: tally("a", "b", "c") }) }));
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "looktest-"));
  const specPath = path.join(dir, "spec.json");
  try {
    fs.writeFileSync(specPath, JSON.stringify(twoViews));
    const out = execFileSync(process.execPath, [LOOK, specPath],
                             { encoding: "utf8" });
    ok("it judges the widest view", out.includes("1440px"), out.split("\n")[1]);
    ok("so a fault only present on the narrow view is not reported",
       !out.includes("shadow tier"), out.slice(0, 90));

    // -------------------------------------------------------- exit codes
    fs.writeFileSync(specPath, JSON.stringify(good({ hover: [] })));
    let code = 0;
    try { execFileSync(process.execPath, [LOOK, specPath], { stdio: "pipe" }); }
    catch (e) { code = e.status; }
    ok("a major exits non-zero, so it can gate a claim", code === 1, code);

    fs.writeFileSync(specPath, JSON.stringify(good({
      reveal: { count: 5, checked: 30, medianTravel: 60,
                typicalDuration: ["0.6s", 5] } })));
    code = 0;
    try { execFileSync(process.execPath, [LOOK, specPath], { stdio: "pipe" }); }
    catch (e) { code = e.status; }
    ok("a minor on its own does not fail the build", code === 0, code);

    fs.writeFileSync(specPath, "{ not json");
    code = 0;
    try { execFileSync(process.execPath, [LOOK, specPath], { stdio: "pipe" }); }
    catch (e) { code = e.status; }
    ok("an unreadable spec exits 2 rather than passing", code === 2, code);

    fs.writeFileSync(specPath, JSON.stringify({ url: "x", views: [] }));
    code = 0;
    try { execFileSync(process.execPath, [LOOK, specPath], { stdio: "pipe" }); }
    catch (e) { code = e.status; }
    ok("a spec with no measured view exits 2, not clean", code === 2, code);

    // A clean page has to say plainly that this is not the same as good.
    fs.writeFileSync(specPath, JSON.stringify(good()));
    const clean = execFileSync(process.execPath, [LOOK, specPath],
                               { encoding: "utf8" });
    ok("a clean result does not claim the page is good",
       clean.includes("a person still has to look at it"),
       clean.split("\n").slice(-3).join(" "));
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }

  const bad = RESULTS.filter((r) => !r).length;
  console.log(`\n${RESULTS.length - bad}/${RESULTS.length} checks passed`);
  process.exit(bad ? 1 : 0);
}

main();
