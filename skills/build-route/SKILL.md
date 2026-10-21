---
name: build-route
description: Decide which of the three routes a piece of website work takes — Lovable (read the project through its MCP first, then one narrow prompt), WordPress (work carefully inside the live install), or built directly here in Claude Code — and never assume the route. Use at the start of any website task, when a new client arrives, or when it is unclear where the site actually lives. Triggers on "website banao", "ye kaam kaise karein", "new client site", "kahan banayein", "lovable ya wordpress", "naya project".
---

# Which route does this work take

Pick the route from evidence, never from memory of a similar project. Two
clients with the same kind of site are often on different stacks.

## Find out first

1. Read the project's `.claude-context/memory/` and `CLIENT-LOG.md`.
2. If the stack is still unclear, run the recon tool — it names the platform
   from the live site:
   `python "C:\Claude-Code\.ai-system\skills\site-recon\recon.py" <domain>`
3. Say which route you are taking and why, before starting.

## Route 1 — Lovable

**When:** the site already lives in a Lovable project, or a new site is being
built there.

**The rule that matters: read the project through the Lovable MCP before
writing anything.** Reading is free. Never describe a change from memory, from
the rendered page, or from how a similar project was built. Open the actual
file and quote the current code in the prompt.

Then write one narrow prompt and stop. Full rules, the stop instruction, the
plan-approval block, the staged whole-site build and the cost discipline are in
`lovable-prompting`.

Afterwards, verify from outside: Lovable saying "done" is a claim, not a fact.
`curl` the live page with JavaScript never executed, open it at 390 and 1440,
and check the build hash changed rather than trusting the deploy message.

## Route 2 — WordPress

**When:** the client's site runs on WordPress, which is most takeovers.

You are working inside a live install that other people also touch. Pull before
you upload, read every save back, bypass the cache before believing anything,
and watch for the en dash WordPress inserts on its own. Full rules in
`wordpress-work`.

Never rebuild a WordPress site as something else because it would be easier.
That is the client's decision, and it carries their URLs, their rankings and
their plugins.

## Route 3 — built directly here

**When:** a greenfield build with no existing site, a mockup or pitch, or
something that genuinely needs code the other two routes cannot carry.

Build it in the project folder as a real app. The house stack, proven on a
build in this workspace:

```
Next.js + React + TypeScript + Tailwind
lenis          smooth scroll
motion         animation
lucide-react   icons (never generated image icons)
```

- `npm run dev`, then look at it in the browser. Do not claim it works from the
  code.
- A framework's own agent instructions in the repo (for example an `AGENTS.md`
  that a dev server writes) override general knowledge. Read them. The version
  in the project may differ from what you remember.
- Everything in `web-build-standards` applies: Lenis with `scroll-behavior:
  smooth` removed, motion on section entry and hover, the 320/360 overflow
  fixes, `100svh` for the hero, no em dashes, SEO at build time.
- Finish with `responsive-qa`, then `launch-files`.

## Mixed situations

These come up constantly and the answer is usually "both, in order":

| Situation | Route |
|---|---|
| WordPress site, new landing page | WordPress, unless the client agreed to host the page elsewhere |
| WordPress site, form stopped working | WordPress; diagnose from the destination backwards |
| Lovable site, content or data change | Often not a prompt at all. Use the project's own MCP or the database directly and spend no credit. |
| New client, no site yet | Direct build for a pitch or mockup; Lovable or WordPress once they are paying and someone has to maintain it |
| Site exists, platform unknown | Recon first. Never guess. |

## Who presses the button, by route

The three routes do not carry the same authority, and this is the part that is
easiest to get wrong once a connector makes everything possible.

| Route | What Claude does | What stays with the user |
|---|---|---|
| Lovable, with a repo | Clones, edits the code, commits, pushes. Lovable publishes it. No prompt, no credit | nothing |
| Lovable, no repo | Reads the project, writes the prompt, saves it in the project folder, says it is ready | **Sending it.** Every time, unless told to send in that same session |
| WordPress | Everything inside the session the user opened: read, analyse, implement, verify | Signing in. Claude never enters a credential or creates an account |
| Direct build | The whole thing: build, run, look at it, fix, verify | Nothing, until it goes anywhere public |

The direct build is the only route where Claude carries the work end to end,
because the only thing at risk is a folder on this machine. The other two touch
something live that somebody is paying for.

## The one rule across all three

Whatever the route, the work is not finished because the tool reported success.
Lovable saying "done", a WordPress save showing a green tick, and a dev server
compiling are all claims. Verify against the live result, with your own eyes,
at real widths. See `verify-before-claiming` and `responsive-qa`.
