---
name: responsive-qa
description: Check a page at real device widths - phone through to a 2560px desktop, never stopping at 1440 - and find the layout, tap-target, image and heading problems a developer would catch by looking — measured, not eyeballed. Use after building or changing any page, before telling the user it works, and whenever they report that something "looks broken" on a phone or tablet. Also use to audit a client's existing site. Triggers on "check responsive", "mobile pe dekho", "test on devices", "koi bug to nahi", "is it working on mobile", "page check karo", or any claim about a page being done.
---

# Responsive QA

## Two things this script does not do

**It runs Chromium only.** Calling a page "checked" after it leaves two
engines untested. Firefox and WebKit are installed alongside Chromium with
Playwright, so run the three-engine pass beside it when a layout matters:

```bash
node "C:\Claude-Code\.ai-system\skills\responsive-qa\crossbrowser.js" <url> \
  --routes /,/about,/contact --out <project>\.claude-context\qa\crossbrowser
```

It opens every route in all three engines at every width, and reports **only
the differences that survive measurement** - status, overflow, h1 size, weight
and font, which image the browser chose off the srcset, broken images,
background. It exits 1 when the engines disagree or a page fails to load.

Measure before reporting a difference between engines. A reduced-scale JPEG
made one engine look like it was missing a bold run; measuring gave the same
weight, the same font and the same width in all three. The script compares
numbers for that reason and never the pictures.

This exists in the house system because a client project needed it, wrote its
own, and that copy quietly drifted: it swept two widths while this one swept
six, so nothing above 1440 was opened in any engine for weeks. **A tool worth
keeping belongs here, with the client's routes passed in as arguments.**

**It does not judge contrast, and sampling pixels will lie to you.** On small
anti-aliased text almost every ink pixel is a partially covered edge pixel, so
a screenshot sample reads far lighter than the real colour. One eyebrow
measured 3.3:1 from pixels and failed; the specified colours put it at 5.97:1
and passing.

WCAG is defined on the specified colours. Read them from the browser:

```js
const c = document.createElement("canvas").getContext("2d");
c.fillStyle = getComputedStyle(el).color;
const [r, g, b] = (c.fillRect(0, 0, 1, 1), c.getImageData(0, 0, 1, 1).data);
```

Walk up from the element for the first non-transparent background. Check the
method on a control first: white on black must come out at exactly 21.00.

A page is not finished because the code looks right. It is finished when it has
been opened at the widths real people use and nothing is broken there.

Never say a page works until this has run and its findings are either fixed or
reported.

## Run it

```bash
node "C:\Claude-Code\.ai-system\skills\responsive-qa\rqa.js" <url> --out <project>\.claude-context\qa\<name>
```

Options: `--widths 360,390,768,1024,1440,1920,2560` (default is all
seven), `--full` for full-page screenshots instead of viewport-only.

**Desktop is checked past 2000px, not stopped at 1440.** A page that
looks right on the laptop it was built on is the usual way a container
with a fixed max-width ships: at 2560 it leaves hundreds of pixels of
white down each side, and nothing below 2000 shows it. Narrowing the
sweep with `--widths` is for re-checking one width after a fix, never
for the first pass.

It writes `report.md`, `findings.json` and one screenshot per width, and exits
**1** when a BLOCKER or MAJOR finding exists. Put the output inside the
project's own folder, never in temp.

## What it measures

| Severity | Checks |
|---|---|
| BLOCKER | sideways scroll (content wider than the viewport); images with a real src that fail to load |
| MAJOR | which element causes the overflow; tap targets under 44x44 on mobile; images with no alt; no visible H1; fixed overlays covering more than 30% of a phone screen |
| MINOR | text under 12px on mobile; images served far larger than displayed; first section taller than the screen; text clipped by a hidden-overflow ancestor; more than one H1 |
| MINOR | **scale and proportion** (see below): hero dead space, a container that never grows, a heading that is not fluid, `overflow-x:hidden` on the root, anchors that overshoot the sticky header |

## Scale and proportion — "bade desktop pe responsive nahi hai"

A page can pass every breakage check and still be wrong, because it does not
use the screen. The report prints the measurements for each width so the
argument is numbers, not impressions:

```
- Hero: 820px tall, 583px of content, 237px empty (align-items: center)
- Content container: 1766px wide (capped at 1766px) in a 1920px viewport
- h1: 59.7px
```

| What it catches | The usual cause and fix |
|---|---|
| Hero dead space that grows with screen height | `align-items: flex-start` on the hero. Centre it vertically; it stays left-aligned horizontally. Then make the padding symmetrical, because asymmetric padding fights the centring. |
| Hero with zero slack on a phone | Fixed inner padding. Scale it: `clamp(40px, 6vh, 72px)` top and bottom. |
| A hero height that is one arbitrary ratio | `min-height: 82vh` is cramped on a 660px laptop and cavernous on a 1400px monitor. Give it a floor and a ceiling and subtract the sticky header: `min(820px, max(560px, calc(100svh - 73px)))`. Read the header height from the live header rather than trusting a number. |
| Container never grows | `max-width: 1200px` is right for a laptop and leaves 670px of white each side at 2560px. Step it up: 1320px at 1600, 1440px at 1920. Then re-check every grid, because a wider container changes how 4-across cards look. The script rates this MINOR, but a client spots it first: pressing Ctrl-minus is the same as a wider viewport (1920 at 50% lays out at 3840), so check 3840 too and treat it as a real finding. |
| Heading identical at 768px and 1920px | One breakpoint and then nothing. Make it fluid with `clamp()` and delete the breakpoint block. Keep the existing line-height and letter-spacing. |
| `overflow-x: clip` or `hidden` on html, phone | The document reports no overflow while content is cut off, so the overflow check passes. Walk elements and flag any right edge past the viewport, skipping those inside an `overflow-x-auto` wrapper. Usual cause: a wide table in a `1fr` grid track; use `minmax(0,1fr)`. |
| `overflow-x: hidden` on body or html | Often hiding nothing, and in several browsers it silently breaks `position: sticky` on descendants. Remove it, then re-check every width for a scrollbar; if one appears, fix the element that is actually too wide instead of masking it again. |
| Anchors landing below the target | `scroll-padding-top` does not match the measured sticky header. Drive both from one CSS variable so they cannot drift apart. |

Screen-reader-only elements (`.sr-only`, `.screen-reader-text`, skip links,
clip-rect hidden) are excluded — they are 1px on purpose. Images with no `src`
yet are treated as lazy-load placeholders, not as broken images.

## After it runs — this is the part that matters

1. **Open the screenshots and look at them.** The script catches measurable
   faults. It cannot tell you the hero reads badly, the spacing is cramped, or
   the colours fight. That is your job, at each width.
2. **Fix what you can fix**, then run it again and show the before/after counts.
   Do not hand back a list of problems you were able to solve yourself.
3. **Report what you did not fix and why** — plainly, not buried.
4. A finding you believe is wrong is a finding to **verify**, not to dismiss.
   Open the page at that width and check with your own eyes before calling it a
   false positive.

## What a finding usually means

- **Sideways scroll** — almost always one element with a fixed width, a long
  unbroken string, a negative margin, or a `100vw` next to a scrollbar. The
  report names the outermost offender; fix that, not its children.
- **Tap target under 44x44** — on a phone this is a thumb that misses. On a
  landing page with a "Call" or "Book Now" button it costs conversions
  directly. Increase padding, not font size.
- **No alt** — an SEO and accessibility fault. Write a real description of the
  image, not the filename.
- **Image far larger than displayed** — slow page, bad Core Web Vitals. Serve a
  correctly sized image or add `srcset`.
- **Hero taller than the screen** — the call to action starts below the fold.
  On PPC landing pages this is a standing rule: the hero must fit.

## Writing the diagnosis

When the fix belongs to someone else, or goes to Lovable as a prompt, write a
diagnosis rather than a vague complaint. The shape that works:

1. **A measurement table first.** Viewport, section height, content height,
   empty space. The numbers are the argument. Say they were measured on the
   live DOM at those sizes, and that they should be re-measured before anything
   changes, because if they have moved the fix moves with them.
2. **One section per issue**: where it is (file and the exact line), what the
   current value is, why it is wrong at both ends of the range, and the
   replacement value.
3. **A "checked and NOT a problem" list.** "The logo and the h1 start at the
   same x, there is no misalignment. Nothing overflows at any width." This
   stops the next person fixing things that are already right, which is where
   regressions come from.
4. **Acceptance criteria per viewport** — what must be true at 1366x660,
   1920x1000 and 2560x1400 afterwards.
5. **An order of work.** Group the changes that interact (hero height, hero
   alignment and hero padding are one change). Separate the ones that alter
   global scale (container width, fluid headings), because widening the
   container changes every grid on the site and deserves its own look.

## Limits — say these rather than overstating

- It renders in Chromium. Safari and Firefox can differ; if the user reports a
  problem on iPhone specifically, that needs a real Safari check.
- It checks one URL at a time. For a whole site, run it per page and collect
  the reports in one folder.
- It cannot judge aesthetics, copy or brand fit.
- It waits for network idle and scrolls the page once to trigger lazy content.
  A page that loads content on a later interaction needs that interaction
  driven separately.
