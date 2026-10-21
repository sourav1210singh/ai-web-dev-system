#!/usr/bin/env node
/**
 * Does study.js measure the numbers that are actually in the page?
 *
 * Runs against fixture.html, whose every value is written down on purpose, so
 * a wrong reading is provable rather than a matter of opinion.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { execFileSync } = require("child_process");

const HERE = __dirname;
const results = [];

function ok(name, cond, extra) {
  results.push(!!cond);
  console.log(`${cond ? "PASS " : "FAIL "} ${name}${extra ? "  [" + extra + "]" : ""}`);
}

const out = fs.mkdtempSync(path.join(os.tmpdir(), "study-"));
const url = "file:///" + path.join(HERE, "fixture.html").replace(/\\/g, "/");

let spec = "";
let code = 0;
try {
  execFileSync(process.execPath,
    [path.join(HERE, "study.js"), url, "--out", out, "--widths", "1440"],
    { encoding: "utf8", stdio: ["ignore", "pipe", "inherit"], timeout: 180000 });
} catch (e) {
  code = e.status == null ? -1 : e.status;
}
try { spec = fs.readFileSync(path.join(out, "spec.md"), "utf8"); } catch (e) {}

ok("it ran and wrote a spec", spec.length > 500, `${spec.length} chars, exit ${code}`);

// type
ok("reads the h1 size and line height", /\*\*h1\*\*.*48px\/56px/.test(spec));
ok("reads the h1 weight", /\*\*h1\*\*.*weight 700/.test(spec));
ok("reads the h1 tracking", /\*\*h1\*\*.*tracking -0\.5px/.test(spec));
ok("reads the h2 size", /\*\*h2\*\*.*32px\/40px/.test(spec));
ok("reads the body size", /\*\*(body|p)\*\*.*18px\/30px/.test(spec));

// colour and shape
ok("normalises colours to hex", /#1f6feb/.test(spec));
ok("does not leave lab() or oklab() in the spec",
  !/(?:ok)?lab\(/.test(spec));
ok("finds the card radius", /Radii:.*12px/.test(spec));
ok("finds the card shadow", /Shadows:.*8px 24px/.test(spec));

// space
ok("finds the 96px section padding", /Section padding:.*96px/.test(spec));
ok("finds the 32px grid gap", /gaps:.*32px/i.test(spec));
ok("finds the 1200px content width", /Content width:.*1200px/.test(spec));

// rhythm: the fixture uses real <section> markup, so this is the good path
ok("finds all three sections", /over 3 sections/.test(spec));
ok("reads the section padding in the table", /\| section \|.*96px\/96px/.test(spec));
ok("names a section by its heading", /Second section heading/.test(spec));
ok("does not cry wrapper on real section markup",
  !/Do not trust this table/.test(spec));

// motion
ok("finds the 300ms button transition",
  /background-color.*\| 0\.3s(, 0\.3s)? \|.*ease-in-out/.test(spec));
ok("finds the 600ms reveal transition", /0\.6s \| cubic-bezier/.test(spec));
ok("finds the keyframe animation by name", /@keyframes drift/.test(spec));
ok("reads the keyframe steps", /translateY\(-12px\)/.test(spec));
ok("finds the 2400ms infinite animation", /drift \| 2\.4s .*infinite/.test(spec));

// scroll reveal
const m = /(\d+) of (\d+) elements below the fold animate in/.exec(spec);
ok("counts the elements that animate in on scroll", m && Number(m[1]) >= 5,
  m ? `${m[1]} of ${m[2]}` : "line not found");
ok("reports the reveal duration", /Typical duration 0\.6s/.test(spec));
ok("reports the reveal easing", /easing cubic-bezier/.test(spec));
ok("measures how far the reveal travels", /median travel (3[5-9]|4[0-5])px/.test(spec));

// hover
ok("measures what changes on hover", /On hover/.test(spec) &&
  /Book a call/.test(spec));
ok("reads the hover colour change", /bg: #1f6feb -> #0b4fc4/.test(spec));
ok("reads the hover scale", /transform:.*matrix\(1\.04/.test(spec));

// sticky header
ok("finds the sticky header", /sticky, 72px/.test(spec));

// reduced motion
ok("checks prefers-reduced-motion", /## Reduced motion/.test(spec));
ok("credits the fixture for respecting it",
  /respects reduced motion/.test(spec));
ok("counts the motion elements on both sides, not distinct rules",
  /Elements with a non-zero transition or animation: \*\*\d+ normally, \d+/.test(spec));
ok("reads the h1 colour as hex", /\*\*h1\*\*.*#16202a/.test(spec));

// honesty
ok("says the numbers are not a substitute for looking",
  /Look at the screenshots/.test(spec));
ok("warns about font licensing", /licensed separately/.test(spec));
ok("a screenshot was actually written",
  fs.existsSync(path.join(out, "study-1440.png")));
// the scroll probe ends at the footer; the screenshot must not
let json = {};
try { json = JSON.parse(fs.readFileSync(path.join(out, "spec.json"), "utf8")); } catch (e) {}
ok("the screenshot is taken from the top of the page",
  json.views && json.views[0] && json.views[0].shotScrollY === 0,
  json.views && json.views[0] ? "scrollY " + json.views[0].shotScrollY : "no json");

fs.rmSync(out, { recursive: true, force: true });
const bad = results.filter((r) => !r).length;
console.log(`\n${results.length - bad}/${results.length} checks passed`);
process.exit(bad ? 1 : 0);
