---
name: lovable-prompting
description: How to write a prompt for the Lovable agent so it costs under a credit, changes only what you asked, and does not burn the budget testing. Covers reading the code free first, the stop instruction, plan-approval blocks, and why Lovable saying "done" is a claim not a fact. Use before sending anything to Lovable, or when asked to write a Lovable prompt, or when a Lovable project needs a change. Triggers on "lovable", "lovable prompt", "lovable me change karo", "credits".
---

# Writing a prompt for Lovable

Credits are the constraint. A sprawling prompt costs eight credits and comes
back having changed things you did not ask for. A narrow one costs under one.

## You write the prompt. You never send it.

Write it, save it in the project, say it is ready, and stop. **Pressing enter
belongs to the user**, every single time.

This holds even when an MCP connector makes sending technically possible.
`send_message` is for reading the project and for the one case where the user
says, in that same session, "upload it and send it". Nothing weaker counts: not
their approval of the work itself, not an obvious one-line fix, not the fact
that they already approved a near-identical prompt a minute ago. If you are
unsure whether you were told to send, you were not.

Two reasons, both real. The prompt changes a live client site, and a prompt
that goes out before the user has read it cannot be called back. And the
credits are theirs, so the moment they are spent is theirs to choose.

This was already the rule here and it was broken once, by using the connector
to send two prompts that had been approved as *work* but not as *sending*.
Approval of the change is not approval to press enter.

## Before you write the prompt

**Read the code through the Lovable MCP first.** Reading is free. Never describe
a change from memory or from the rendered page — open the actual file and quote
the current code in the prompt. Half the wasted credits come from a prompt that
describes a file wrongly.

Save every prompt as a file in the project's `lovable-prompts/` folder, numbered
in order. The user pastes them one at a time and the numbering is the history.

## The shape of a good prompt

1. **One concern.** Bugs or structure, never both. Say the rest follows in a
   separate prompt.
2. **Quote the current code** and the exact replacement. Not "update the hero" —
   show the block.
3. **Name what must not change**, by file and by component. Lovable will
   otherwise tidy adjacent code.
4. **Give the acceptance check** — the specific thing that proves it worked.
5. **End with the stop instruction.**

```
Make the change and stop. Do not run tests or curl commands. Do not poll the
backend. Do not write a report.

If this cannot be done as described, stop and say so in one sentence.
```

That block matters. Without it the agent will verify, poll, retry and write a
summary, all on your credits, and the verification is not even trustworthy.

## Verify it yourself afterwards

**Lovable saying "done" is a claim, not a fact.** Check from outside:

- `curl` the live page and read the raw HTML, with JavaScript never executed
- open it in a browser at 390 and 1440 and look
- check the build hash changed, not that the deploy reported success

A stale cache has twice made a landed fix look like it did not land. Check the
hash first.

## Known blockers

| Thing | What happens |
|---|---|
| Plan approval | The agent pauses for a plan the **user** must click. A sent prompt can sit waiting indefinitely and look like silence. Tell the user when this is likely. |
| Build steps that overwrite output | A build plugin was rewriting `public/sitemap.xml` on every build, so source edits never appeared. Look for one before concluding a fix did not publish. |
| Static-file handler ordering | A file served at the exact path answers before the route does, so the "correct" generated file is never reached. |
| First navigation away from a dynamic route throwing | Arriving is fine, clicking away throws. A pasted URL works and a click does not, because a fresh load only hydrates. |

## Scope lines that have earned their place

Copy these into prompts when they apply:

- Do not change slug, published date, published at, or status on any row.
- Do not touch the enquiry form, its server handler, or the CRM submission.
- Do not add any redirecting URL to the sitemap.
- Only write the fields that are passed. A missing field must never be nulled.
- Do not break the existing block handling — tables, blockquotes, headings and
  lists already render correctly and must continue to.
- Everything confirmed working in the earlier prompts must not regress.

## Building a whole site: stage it

A full site is not one prompt. Write a numbered sequence, each one pasted after
the previous has finished and its preview has been checked. The sequence that
worked:

| Step | What |
|---|---|
| 1 | Foundation: stack, design tokens, typography, spacing, buttons, header, footer, reusable CTA band and section heading, routing with placeholder pages. **Build no page content yet.** |
| 2 | Images, with the rules from `ai-image-direction` |
| 3-8 | One page per step, in order |
| 9 | Final QA and polish: responsive, SEO, performance, accessibility, 404, motion, content audit |

Rules that make it work:

- **Every step is self-contained.** All the copy lives inside the prompt. The
  user never has to supply content separately or paste two things at once.
- **Upload brand assets before step 1** and name them in the prompt, so the
  logo and favicon are never generated.
- Put the design tokens in step 1 as literal values: hex codes with what each
  one is for, type sizes for desktop and mobile, section padding, container
  width, button padding and radius. Vague direction produces a generic site.
- Carry a short **non-negotiables block** in step 1 that applies to the whole
  project: one h1 per page, semantic HTML, no horizontal scroll at 375/768/
  1024/1440, alt text on every image, visible focus rings, WCAG AA,
  `prefers-reduced-motion` respected.
- State the feeling in one line. "A boutique advisory firm that charges well and
  does not need to shout. Restraint is the brief. When unsure, remove something
  rather than add something." That line does more work than a page of adjectives.
- End the sequence with a **content audit** (see `client-content-audit`) listing
  what must not exist: invented statistics, testimonials nobody supplied, fake
  contact details, lorem ipsum.

For round two, after client feedback, number the prompts again and keep them
equally narrow: one fix, one article, one page per prompt.

## Cost discipline

- Read free, write once. Never send a prompt to "have a look".
- Batch related small edits into one narrow prompt rather than five.
- If the change is data, not code, do it through the project's MCP or the
  database directly instead of spending a credit.
- When the user is out of credits, write the prompt to a file and tell them it
  is ready to paste rather than sending it.
