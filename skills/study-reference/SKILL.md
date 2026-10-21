---
name: study-reference
description: Measure a reference page instead of guessing at it - type scale, colour, spacing, radii, shadows, container width, section rhythm, every transition and animation with its real duration and easing, what changes on hover, what animates in on scroll and how far it travels. Use when a client sends a site they like, when working from a bought template, when matching a competitor's standard, or before rebuilding any page whose look matters. Triggers on "reference", "template", "iske jaisa banao", "same as this site", "animation chahiye", "competitor", "inspiration", "aise dikhna chahiye".
---

# Measure the reference, do not eyeball it

"Make it like this site" produces something a bit like that site. Close
spacing, nearly the right weight, animation that feels heavy because it runs
at 1000ms where the reference ran at 450ms with a different easing curve. All
of it is invisible in a side-by-side description and obvious to the client.

Everything that makes a reference feel the way it does is a number, and all of
those numbers can be read straight off the rendered page.

```bash
node "C:\Claude-Code\.ai-system\skills\study-reference\study.js" <url> --out <project>\.claude-context\reference
```

Writes `spec.md`, `spec.json` and a screenshot per width. Default widths are
390 and 1440.

## Use it only where you are entitled to

It records a spec. It does not copy markup, CSS, images or fonts, and neither
should you. A bought template licensed to the client is fair game. A
competitor's site is fair for *standards* - how fast their page feels, what
their type scale is - not for lifting their design. Fonts are licensed
separately from everything else; check before using the same family.

## What you get

**Tokens** — type scale per role with family, size, line height, weight and
tracking; colour palette normalised to hex, because modern stylesheets compute
to `oklab()` which nobody can build from; radii; shadows; borders; gradients;
flex and grid gaps; section padding; content width.

**Rhythm** — section heights as a multiple of the viewport, their padding and
their headings. If the page has no `<section>` markup the table says *do not
trust this table* and tells you to read the rhythm off the screenshot. Believe
it when it says that.

**Motion** — every transition and animation with its property, duration,
easing and delay, with the keyframes. Then the measured behaviour: how many
elements animate in on scroll, the typical duration and easing, the median
distance they travel, and what actually changes on hover with the before and
after values.

**Reduced motion** — the page is loaded a second time with
`prefers-reduced-motion: reduce` and the elements carrying motion are counted
both times. A reference that does not switch its motion off is common; the
report says so, and you do not copy that.

## Then build, then measure your own

The loop that makes this worth running:

1. Study the reference.
2. Round the numbers to a scale of your own. 23px of padding in a reference is
   24px in a system. Keep the ratios, not the accidents.
3. Build.
4. **Run the same script on your own build** and put the two specs side by
   side. That is numbers against numbers, which is the only comparison that
   settles an argument about whether it matches.
5. Then look at both screenshots, because a page can match every number and
   still read wrong. See `verify-before-claiming`.

## What it cannot do

- It measures what rendered at that width at that moment. A carousel caught
  mid-slide, a cookie banner covering the hero, an A/B variant: all possible.
  Look at the screenshot before trusting the numbers.
- It cannot tell you *why* a choice was made, or which parts are good.
- Motion that only fires on a click, a drag or a form step is not probed. For
  those, drive the page in the browser and watch.
- A page behind a login has to be captured a different way.

## Writing the build prompt from it

Give the agent the numbers, not the URL. "Hero h1 at clamp between 40 and
96px, weight 700, tracking -2%, line height 1.0; sections 96px top and bottom;
cards 12px radius with a 0 8px 24px shadow at 12% black; reveal on scroll at
600ms cubic-bezier(0.4, 0, 0.2, 1) with 40px of travel, disabled under
prefers-reduced-motion." That prompt produces the same page twice. "Make it
like example.com" does not.
