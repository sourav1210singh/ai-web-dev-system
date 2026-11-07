/**
 * Does the DESIGN.md generator report what was measured, and refuse to invent
 * the rest?
 *
 * The risk with a document like this is not that it crashes. It is that it
 * reads as authoritative while carrying a guess, which is worse than no file
 * at all, because the next person builds on it.
 *
 *   node designmdtest.js
 */
const path = require("path");
const m = require(path.join(__dirname, "designmd.js"));

const RESULTS = [];
function ok(name, cond, extra) {
  RESULTS.push(!!cond);
  console.log(`${cond ? "PASS " : "FAIL "} ${name}${extra ? "  [" + extra + "]" : ""}`);
}

// A page measured the way study.js really measures one: tallies are
// [{ value, count }], not [value, count]. A fixture invented from memory
// used pairs, every test passed, and the first real run produced a file
// with every token blank.
const SPEC = {
  url: "https://example.test/",
  measuredAt: "2026-11-07",
  type: {
    h1: { family: "Inter", size: "48px", weight: "700", lineHeight: "56px",
          letterSpacing: "-1px", transform: "none", color: "#111111",
          sample: "Build something real" },
    h2: { family: "Inter", size: "32px", weight: "600", lineHeight: "40px",
          letterSpacing: "0px", transform: "none", color: "#111111", sample: "Why us" },
    body: { family: "Inter", size: "16px", weight: "400", lineHeight: "26px",
            letterSpacing: "0px", transform: "none", color: "#444444",
            sample: "We do the work" },
    button: { family: "Inter", size: "16px", weight: "500", lineHeight: "24px",
              letterSpacing: "0px", transform: "uppercase", color: "#ffffff",
              sample: "Get started" },
  },
  sizes: [{ value: "16px", count: 120 }, { value: "48px", count: 2 }, { value: "32px", count: 6 }],
  families: [{ value: "Inter", count: 180 }],
  weights: [{ value: "400", count: 120 }, { value: "700", count: 8 }],
  foreground: [{ value: "#444444", count: 90 }, { value: "#111111", count: 40 }, { value: "#8a8a8a", count: 12 }],
  background: [{ value: "#ffffff", count: 200 }, { value: "#f6f6f6", count: 24 }, { value: "#e8442f", count: 6 }],
  borders: [{ value: "1px solid #e5e5e5", count: 30 }],
  gradients: [],
  radii: [{ value: "0px", count: 50 }, { value: "8px", count: 20 }, { value: "16px", count: 8 }, { value: "9999px", count: 4 }],
  shadows: [{ value: "rgba(0,0,0,0.08) 0 2px 6px 0", count: 12 }],
  gaps: [{ value: "8px", count: 20 }, { value: "16px", count: 40 }, { value: "24px", count: 18 }, { value: "32px", count: 10 }],
  sectionPadding: [{ value: "64px", count: 8 }, { value: "96px", count: 4 }],
  container: [{ value: "1200px", count: 6 }],
  transitions: [{ value: "color 200ms ease", count: 20 }],
  animations: [],
};

// --- the base unit, which decides every component's padding -----------
ok("an 8px scale is read as 8", m.baseUnit([8, 16, 24, 32, 48]).unit === 8);
ok("a 4px scale is read as 4", m.baseUnit([4, 12, 20, 28]).unit === 4,
   String(m.baseUnit([4, 12, 20, 28]).unit));
ok("a 2px micro-step is noticed", m.baseUnit([2, 8, 16, 24]).micro === true);
ok("a scale nothing fits reports low coverage",
   m.baseUnit([7, 13, 19, 23]).coverage < 0.5,
   String(m.baseUnit([7, 13, 19, 23]).coverage));

// --- colour naming ----------------------------------------------------
const c = m.nameColours(SPEC);
ok("the most common background becomes the canvas", c.canvas === "#ffffff", c.canvas);
// The most frequent foreground is the running text, not the headline colour.
ok("the darkest foreground becomes the ink", c.ink === "#111111", c.ink);
ok("the most frequent foreground becomes body", c.body === "#444444", c.body);
ok("a lighter foreground becomes muted", c.muted === "#8a8a8a", c.muted);
// A page is mostly greys and one colour that means something. Picking the most
// frequent value returns a grey and calls it the brand.
ok("the saturated colour becomes primary, not the frequent grey",
   c.primary === "#e8442f", c.primary);
ok("on-primary is the side that actually contrasts",
   m.contrast(c.primary, c["on-primary"]) >= m.contrast(c.primary,
     c["on-primary"] === "#ffffff" ? "#000000" : "#ffffff"),
   `${c["on-primary"]} at ${m.contrast(c.primary, c["on-primary"])}:1`);
ok("the border colour is kept as the hairline", c.hairline === "#e5e5e5", c.hairline);
ok("contrast is computed correctly", m.contrast("#ffffff", "#000000") === 21,
   String(m.contrast("#ffffff", "#000000")));
ok("a grey is not mistaken for a brand colour", m.sat("#8a8a8a") < 0.1);

// --- the document -----------------------------------------------------
const doc = m.build(SPEC, "Example");
ok("it opens with front matter a parser can read", doc.startsWith("---\n"));
ok("the source page is recorded", doc.includes("https://example.test/"));
ok("the date it was measured is recorded", doc.includes("2026-11-07"));
ok("an h1 becomes the display token", doc.includes("display-xl"));
ok("a button keeps its role", doc.includes("button-md"));
ok("uppercase is carried through", doc.includes("textTransform"));
ok("measured spacing becomes named tokens",
   /spacing:\n\s+xxs: "8px"/.test(doc) || /xxs: "8px"/.test(doc), "8px first step");
ok("the pill radius is named full", /full: "9999px"/.test(doc));
ok("it tells you to reference tokens rather than raw values",
   doc.includes("{colors.primary}") && doc.includes("never raw values"));
ok("it says what it did not measure",
   doc.includes("## Not measured") && doc.includes("Focus states"));
ok("component padding is never invented",
   doc.includes("were **not measured**") && !/padding: \d+px \d+px/.test(doc));
ok("the base unit is stated with its coverage",
   /Base unit:\*\* 8px - it divides 100%/.test(doc),
   (doc.match(/Base unit.*/) || [])[0]);
ok("section padding is judged against a reference range",
   doc.includes("SaaS marketing 80-96px"));
ok("it asks for the font substitute to be named",
   doc.includes("brand font is not licensed"));

// --- the honesty checks fire only when they should --------------------
const oneShadow = m.build(SPEC, "x");
ok("one shadow is not called drift", !oneShadow.includes("usually drift, not a ladder"));
const many = m.build({ ...SPEC, shadows: [{ value: "a", count: 1 }, { value: "b", count: 1 }, { value: "c", count: 1 }, { value: "d", count: 1 }] }, "x");
ok("four shadow tiers are called drift", many.includes("usually drift, not a ladder"));
const none = m.build({ ...SPEC, shadows: [] }, "x");
ok("a flat page is described as flat, not given shadows",
   none.includes("No shadows were measured"));

const drifted = m.build({ ...SPEC, sizes: Array.from({ length: 14 },
  (_, i) => ({ value: `${10 + i}px`, count: 3 })) }, "x");
ok("fourteen font sizes are called drift", drifted.includes("distinct font sizes"));
ok("four font sizes are not", !m.build(SPEC, "x").includes("distinct font sizes"));

const messy = m.build({ ...SPEC, gaps: [{ value: "7px", count: 2 }, { value: "13px", count: 2 }, { value: "19px", count: 2 }],
                        sectionPadding: [{ value: "23px", count: 1 }] }, "x");
ok("a page with no real scale says so",
   messy.includes("not on a consistent scale"));

const still = m.build({ ...SPEC, transitions: [], animations: [] }, "x");
ok("a page with no motion is not given any",
   still.includes("Do not add motion that the reference"));


// --- the shape study.js actually writes -------------------------------
// This is the check that was missing. The generator was handed a flat object
// in every test and the real file nests the measurements under `tokens`, one
// view per width, so the first real run wrote a document with every token
// blank while 34 checks stayed green.
const REAL = {
  url: "https://example.test/",
  measured: "2026-11-07T10:00:00.000Z",
  reduced: { verdict: "most motion is switched off" },
  views: [
    { width: 390, status: 200, tokens: { ...SPEC, container: [{ value: "360px", count: 2 }] },
      motion: { transitions: [], animations: [] } },
    { width: 1440, status: 200, tokens: SPEC,
      motion: { transitions: [{ value: "color 200ms ease", count: 9 }], animations: [] } },
  ],
};
const realDoc = m.build(REAL, "Real");
ok("the nested shape study.js writes is understood",
   realDoc.includes("#e8442f") && realDoc.includes("display-xl"),
   realDoc.includes("#e8442f") ? "tokens present" : "TOKENS EMPTY");
ok("the colours are not left blank",
   /colors:\n\s+canvas: "#ffffff"/.test(realDoc));
ok("the widest view is the one described",
   realDoc.includes("describes: 1440px viewport"),
   (realDoc.match(/describes:.*/) || ["none"])[0]);
ok("the other widths studied are named",
   realDoc.includes("390, 1440"));
ok("motion is read from its own section",
   realDoc.includes("color 200ms ease"));
ok("the reduced-motion verdict is carried through",
   realDoc.includes("most motion is switched off"));
ok("a run where every view failed does not pretend to have measured one",
   m.build({ url: "u", measured: "2026-11-07", views: [{ width: 390, error: "boom" }] }, "x")
     .includes("## Not measured"));

// --- a dark ink is not a brand colour ---------------------------------
// Saturation climbs as a colour darkens, so a near-black navy reads 0.88 and
// would be picked ahead of the real accent. Chroma separates them.
ok("saturation alone would be fooled by a dark navy", m.sat("#061b31") > 0.8);
ok("chroma is not", m.chroma("#061b31") < 0.2, String(m.chroma("#061b31")));
const navy = m.nameColours({
  background: [{ value: "#ffffff", count: 90 }, { value: "#273951", count: 20 }],
  foreground: [{ value: "#061b31", count: 80 }, { value: "#533afd", count: 9 }],
  borders: [],
});
ok("the vivid colour is chosen as primary over the navy",
   navy.primary === "#533afd", navy.primary);

const bad = RESULTS.filter((r) => !r).length;
console.log(`\n${RESULTS.length - bad}/${RESULTS.length} checks passed`);
process.exit(bad ? 1 : 0);
