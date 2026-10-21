---
name: web-build-standards
description: The house defaults for every website built or changed here — smooth scroll with Lenis, motion instead of a flat page, the small-phone overflow fixes, hero that fits the screen, no AI-tell punctuation or styling, SEO basics at build time, and forms that actually submit. Apply these without being asked on any new site, page, section or redesign, in Lovable, WordPress, Webflow, Next or plain HTML. Triggers on "website banao", "page banao", "landing page", "redesign", "section add karo", "flat lag raha hai", "animation nahi hai", "build a site", or any request that produces front-end output.
---

# House build standards

Every one of these exists because it was asked for on a real project, usually
more than once. Apply them by default. If one does not fit, say which and why
rather than skipping it silently.

---

## 1. The page must not feel flat

The exact complaint, 2026-10-06: *"tumne jo banaya h wo website flat lag raha h
koi animation nahi and scroll karne pe glide kare like lenis ka use karo."*

**Smooth scroll — Lenis.** On any React/Next/Lovable build, add Lenis at the
root so the page glides instead of jumping.

```bash
npm i lenis
```

Mount it once in a client component at the layout root, start a RAF loop, and
destroy on unmount.

**Three gotchas that have already cost time:**

| Gotcha | What happens |
|---|---|
| `scroll-behavior: smooth` in your CSS | Fights Lenis and makes scrolling feel broken. **Remove it** from `globals.css` wherever Lenis is used. |
| Testing by jumping in dev-tools | Bypasses Lenis entirely, so it looks like it is not working. **Scroll with the mouse wheel** to test. |
| Anchor links | Native `#hash` jumps skip Lenis. Route them through `lenis.scrollTo(target)`. |

**Motion.** A static page reads as AI-made. Add, at minimum:

- Section reveal on scroll: fade + 16-24px rise, 500-700ms, a soft ease such as
  `cubic-bezier(0.16, 1, 0.3, 1)`, staggered 60-100ms between siblings.
- Hover on anything clickable: a lift of 4-8px, or a scale of 1.02-1.03, plus a
  shadow change. 150-250ms.
- Image hover: a slow zoom to 1.05 inside `overflow:hidden`.

Use `framer-motion` / `motion` for React, or an IntersectionObserver with CSS
transitions for plain HTML and WordPress.

**Always respect `prefers-reduced-motion`.** Wrap reveals and parallax in
`@media (prefers-reduced-motion: no-preference)` and disable Lenis when the user
asks for reduced motion. Skipping this is an accessibility failure, not a style
choice.

**Sticky header.** A header that reacts to scroll was asked for repeatedly — for
example *"scroll karne pe pill shape me ho jaye, centre me ho jaye"*: full-width
and flush at the top, then on scroll it pulls into a centred rounded pill with a
max width and a blurred background. Transition the width, radius, padding and
background, not `position`.

---

## 2. Responsive is a hard requirement, not a pass

The rule is: **open it at 320px and 360px and nothing may be wider than the
screen.** 360px is the most common Android width and it is where the bugs are.

Run the QA before claiming anything — see the `responsive-qa` skill.

**The overflow fixes that solved this on a live site** (measured at 320 and
360px, desktop unchanged) — start from these, then re-measure:

```css
/* grid and flex children refuse to shrink below their content without this */
.grid > *, .flex-row > * { min-width: 0; }

/* long unbroken words and headings */
h1, h2, h3 { overflow-wrap: break-word; }
@media (max-width: 480px) { h1, h2, h3 { hyphens: auto; } }

/* label/value rows that cannot wrap */
.row { flex-wrap: wrap; }
.row b, .row a { overflow-wrap: anywhere; }

/* two up instead of four on a phone */
.stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }

/* long button text pushing the second button off screen */
.hero-cta .btn { white-space: normal; text-align: center; justify-content: center; }
```

`min-width: 0` on grid/flex children fixes more overflow than anything else.
Reach for it first.

**Hero must fit the first screen.** Standing rule on every landing page: the
whole hero — heading, copy, CTAs, form button — visible with no scrolling, on
any device.

```css
.hero { min-height: calc(100vh - var(--header-h));
        min-height: calc(100svh - var(--header-h)); }
```

`svh` matters: on mobile browsers `vh` includes the address bar, so `100vh`
alone pushes the CTA under it. On short laptops (max-height ~900px) compress the
padding rather than letting the hero grow.

Also: tap targets 44x44 minimum, body text never below 14px on mobile (12px is
the absolute floor), and test a real 320px width, not just the dev-tools preset.

---

## 3. It must not read or look AI-made

A client once called a mockup *"designed by AI"* and the project was nearly
lost. That is the bar.

**Punctuation.** No em dash (—, `&#8212;`, U+2014) and no en dash (–, `&#8211;`)
anywhere in client-facing copy. This has been asked for on 12 projects.

> **Gotcha:** dashes are often stored as the HTML entity `&#8212;`, so searching
> for the literal character finds nothing. Search for both the character and the
> entity, in the database as well as the source.

Replace with a comma, a colon, a full stop or a rewritten sentence — not with a
hyphen surrounded by spaces, which is its own tell.

**Other tells to avoid:** emoji in body copy, "startup gradient" purple-to-blue
washes, playful 3D illustrations, "Unlock/Supercharge/Elevate your..." headlines,
three-column feature grids with generic icons, and stock photos that are
obviously AI-rendered.

**Facts.** Never invent company history, founding dates, certifications, licence
numbers, team names or review counts. A mockup once carried an invented history
and a competitor's ownership model. Put a clearly marked placeholder and ask,
every time.

---

## 4. SEO is part of the build, not a later pass

Ship every page with these already in place. The full audit lives in the
`seo-complete` skill; this is the build-time minimum:

- One visible `<h1>`, and headings in order with no skipped levels
- `<title>` under ~60 characters, meta description 150-160, both unique per page
- `alt` on every content image, describing the image, never the filename.
  Decorative images get `alt=""`.
- Canonical URL, `lang` attribute, favicon, OG and Twitter image
- JSON-LD appropriate to the page: Organization or LocalBusiness, Service,
  Article, FAQPage, plus BreadcrumbList
- Internal links to the related pages, with real anchor text
- Images sized for their slot with `srcset`, `loading="lazy"` below the fold,
  and explicit `width`/`height` so the layout does not shift

On a rebuild, nothing the old page ranked for may silently disappear — use the
`migration-parity` skill.

---

## 5. Forms have to actually submit

Forms are the most common thing to break here: 396 mentions across 18 projects.

**Never claim a form works without submitting a real test and confirming the
submission arrived** — the row in the database, the email in the inbox, the
entry in the admin. Seeing a success message is not confirmation.

Known traps already hit:

| Trap | Where |
|---|---|
| WPForms HTML pasted as static markup — the nonce is dead and submissions silently vanish | WordPress |
| reCAPTCHA token expiring before submit, giving "error trying to send your message" | any |
| Synthetic JS clicks in the WP admin that look saved but are not | WordPress |
| Replacing a page and losing the lead form that was quietly working | landing pages |

Also check: a real success state, visible validation messages, labels bound to
inputs, correct `type` and `autocomplete`, and no `required` field that cannot be
completed on mobile.

---

## 6. Per stack

**Lovable / React / Next** — Lenis, framer-motion, Tailwind, shadcn all apply
directly. Read the code free through the Lovable MCP before spending credits,
and keep the prompt narrow. Lovable's agent pauses for plan approval that only
the user can click, so a sent prompt may sit waiting. Lovable saying "done" is a
claim to verify, not a fact.

**WordPress** — no npm. Use an IntersectionObserver plus CSS transitions for
reveals, and a small vanilla smooth-scroll instead of Lenis unless the theme
already bundles it. Put CSS in the child theme, never in the parent. On a server
the client also edits, pull before uploading or their work is destroyed.

**Webflow** — native interactions instead of libraries; header and footer are
components, and shared classes need combo classes rather than edits.

---

## Before saying a page is done

1. `responsive-qa` has run and its blockers and majors are fixed
2. Scrolled with the mouse — it glides, sections reveal, hovers respond
3. Hero fits the first screen at 390px and on a 900px-tall laptop
4. Searched for em dash and en dash, as characters **and** as entities
5. A real form submission was made and its arrival confirmed
6. Title, description, H1, alts, canonical, schema in place
7. Screenshots taken at 390, 768 and 1440 and actually looked at
