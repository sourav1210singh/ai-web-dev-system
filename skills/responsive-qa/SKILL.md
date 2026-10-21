---
name: responsive-qa
description: Check a page at real device widths and find the layout, tap-target, image and heading problems a developer would catch by looking — measured, not eyeballed. Use after building or changing any page, before telling the user it works, and whenever they report that something "looks broken" on a phone or tablet. Also use to audit a client's existing site. Triggers on "check responsive", "mobile pe dekho", "test on devices", "koi bug to nahi", "is it working on mobile", "page check karo", or any claim about a page being done.
---

# Responsive QA

A page is not finished because the code looks right. It is finished when it has
been opened at the widths real people use and nothing is broken there.

Never say a page works until this has run and its findings are either fixed or
reported.

## Run it

```bash
node "C:\Claude-Code\.ai-system\skills\responsive-qa\rqa.js" <url> --out <project>\.claude-context\qa\<name>
```

Options: `--widths 360,390,768,1024,1440,1920` (default is all six),
`--full` for full-page screenshots instead of viewport-only.

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
| Container never grows | `max-width: 1200px` is right for a laptop and leaves 670px of white each side at 2560px. Step it up: 1320px at 1600, 1440px at 1920. Then re-check every grid, because a wider container changes how 4-across cards look. |
| Heading identical at 768px and 1920px | One breakpoint and then nothing. Make it fluid with `clamp()` and delete the breakpoint block. Keep the existing line-height and letter-spacing. |
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
