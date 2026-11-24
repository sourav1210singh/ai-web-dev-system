# Where to find a reference, and what you are allowed to take

A site built without a reference comes out generically correct and forgettable.
Every value is defensible and the whole thing is dull, because nothing set a
standard. This file is the standard: open real work first, pick a direction,
then measure it.

**The rule. Before building any page, open three to five references, choose one
direction with the user, and measure it with `study.js` into `DESIGN.md`.**
Never build from an impression of a site. `study-reference` exists because the
numbers are what make a reference feel the way it does.

Everything below was opened on 24 November 2026 and the access notes are what
actually happened, not what the sites claim. Access terms change, so when one
behaves differently, correct this file.

---

## 1. Two sources an agent can query directly

These are the ones that need no human in the loop.

- **One Page Love MCP**, `onepagelove.com/mcp`. Free during beta, **no account
  and no API key**, rate limited. It exists for exactly this: give an agent
  real websites to study before it designs. Connecting it makes the tools
  available, it does not force their use, so the request has to say to research
  references first.
- **Aceternity UI**, `ui.aceternity.com`. The free plan includes **MCP access
  for Claude Code** and 100+ free components.

## 2. Galleries, for choosing a direction

- `recent.design` covers web, interface, branding, motion, illustration and
  print. `godly.website` now redirects here.
- `refero.design` is indexed by **flow**, not by looks: onboarding, logging in,
  checkout, password reset, billing, empty states. This is the one that answers
  "how should this screen actually work", which is usually the real gap.
- `siteinspire.com` browses free, sign in only to save.
- `httpster.net`, 3,116 sites, typographic, minimal and brutalist leaning.
- `minimal.gallery`, tagged by industry and page type.
- `lapa.ninja`, 7,300+ landing pages, free to browse, sells templates at
  roughly $29 to $129.
- `landingfolio.com`, 961 landing pages plus components and templates.
- `saasframe.io` for SaaS screens. Browsing and search are free, Pro unlocks
  full flows, mobile versions and copy into Figma.
- `tympanus.net/codrops` for motion. Webzibition is 2,000+ handpicked sites,
  and the case studies explain how an effect was built, which is worth more
  than the effect.

**Open these in a browser, they do not read for a scraper:**

- `land-book.com` renders nothing to a fetch.
- `awwwards.com` answered **403** to ours on 24 Nov.
- `cssdesignawards.com` answered **502** on 24 Nov.

**`mobbin.com` is 600,000 screens, but read the tier before relying on it:**
on the free plan Apps are limited and **Sites are not included at all**. For
website reference work it needs Pro. Do not plan around Mobbin unless the
account is paid.

## 3. Components that can ship, with the licence read

Read from each project's own `LICENSE` file on 24 Nov 2026, not from a badge.

**Plain MIT, safe for client work:**

| Source | What it is |
|---|---|
| `ui.shadcn.com` | The base. Components you own and edit, not a dependency |
| `daisyui.com` | Tailwind plugin, pure CSS components |
| `flowbite.com` | 600+ components, sections and pages, Figma designs too |
| `hyperui.dev` | Every example passes axe WCAG 2.1 AA, has dark mode and RTL |
| `magicui.design` | 150+ animated components, built to pair with shadcn |
| `motion.dev/examples` | Copy-paste React, JS and Vue animation snippets |
| `uiverse.io` | Open source elements, MIT stated on their licence page |

**Not plain MIT. Read these before using them:**

- **Preline** is dual licensed, MIT plus a "Preline UI Fair Use License". Free
  for commercial projects, but it may not be used to build a product that
  competes with Preline. Fine for a client site, not for a product we sell.
- **React Bits** is MIT plus a **Commons Clause**. Commercial use is allowed,
  including paid client sites, but you may not sell, sublicense or redistribute
  the components, the tools or the exports as a pack of their own.
- **Aceternity UI** publishes terms of website use, not a component licence.
  The free components are offered for any React or Next.js project; for paid
  client work the one-time all-access tier is the clean route.
- **Cruip** templates: GitHub reports **no licence** on their open template
  repository, so check the licence of the specific template before shipping it.

## 4. Template marketplaces, for a starting structure

`framer.com/marketplace/templates` (free and paid), `webflow.com/templates`
(7,000+), `astro.build/themes`, `vercel.com/templates`, `themeforest.net`.

A bought template licensed to the client is fair game, which the skill already
says. A template licensed to us is not automatically licensed to them, so the
licence goes in the project record with who it was bought for.

## 5. What happens after the pick

```bash
node "C:\Claude-Code\.ai-system\skills\study-reference\study.js" <url> --out <project>\.claude-context\reference
```

That writes `spec.md`, `spec.json`, `DESIGN.md` and a screenshot per width.
Build from the DESIGN.md, not from the screenshot.

**Measure, do not lift.** Reading a competitor's type scale and spacing is
research. Copying their layout and words is not, and the line is in the skill
above. Record in the project's memory which reference was chosen and why, so
the second page matches the first.
