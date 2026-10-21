# An AI system for building client websites

I build websites for clients using AI. Not by pasting prompts and hoping, but
with a system that carries what every project already knows, checks its own
work before it claims anything, and refuses to ship the things that make a site
look AI-made.

This repository is that system: 22 skills, one agent, four hooks and twelve
tools, all built out of real client work and the mistakes it produced.

---

## The problem it solves

Three things kept costing me time and credibility.

**Context died.** Claude Code keeps its transcripts on the machine, keyed to
the account and the working directory. Hit a usage limit, log in with another
account, and months of project knowledge is gone. Across 23 client folders,
the phrase "go and look / check / verify" appeared **408 times** in my own
history. I was re-typing the same instructions forever.

**Claude claimed things it had not checked.** A stale browser cache made a
landed fix look like it had not landed, twice. A stripped URL parameter made a
live video look deleted. A mockup once carried an invented company history and
a competitor's ownership model, and the client called the work "designed by AI".

**Every rule lived in one project.** The same "verify before you tell me
anything" instruction had been written into **seven** different projects by
four different people, because there was nowhere shared to put it.

---

## How it is built

Three layers, deliberately separate.

```
MCP connectors        tools with an API: publish a post, read a database
   (account level)

Skills                procedure and judgement: how the work is done
   ~/.claude/skills/

Hooks                 the parts that must never be skipped
   settings.json
```

An MCP gives a model **tools**. Most of what matters here is not a tool, it is
**procedure** — "test it three different ways", "look at it before and after",
"say what is fact and what is assumption". That belongs in skills. And the part
that must never be skipped belongs in hooks, because a rule in a document is
forgotten once the context fills up, while a hook fires every single time.

Master copies live in the project folder, so they travel with it and survive an
account switch. `install.py` copies them to where Claude Code loads them from,
verifying every file by checksum.

---

## The skills

### Discipline

| Skill | What it enforces |
|---|---|
| `fix-job` | Runs client work as a job with state, in three types: `fix` (something live is wrong), `intake` (a new client: read everything, change nothing) and `golive` (the launch gate, which refuses to close while a blocker stands). Every check runs at once and verify diffs against the before snapshot. |
| `verify-before-claiming` | Nothing is reported as done, fixed, working or live until that work has been checked from more than one angle and the result looked at. Carries the proof table, by kind of claim. |
| `scope-discipline` | Change only what was asked. Capture the rendered HTML before, diff it after; anything but a whitespace difference is a regression. Report what changed, what did not, and what you noticed and left alone. |
| `copy-standards` | No em or en dashes, no AI filler vocabulary, no invented facts. Clearly marked placeholders instead of plausible-sounding inventions. |
| `skill-precedence` | What happens when two skills both apply: the one that knows how a system is operated, and the one that sets what good work is. The second does not lose for being less specific. |
| `client-reply` | Plain English, no markdown so it pastes into email unchanged, and nothing claimed that was not tested first. |

### Quality

| Skill | What it does |
|---|---|
| `responsive-qa` | Opens a page at six real widths and measures what a developer would catch by looking: sideways scroll and the element causing it, tap targets under 44x44, broken images, missing alt, hero dead space, a container that never grows, a heading that is not fluid, `overflow-x:hidden` breaking a sticky header. Exits non-zero on a blocker, so it can gate a claim. |
| `web-build-standards` | The house defaults: smooth scroll with the gotchas that waste a day, the overflow fixes measured at 320 and 360px, `100svh` for a hero that must fit, motion that respects `prefers-reduced-motion`. |
| `seo-complete` | Title and meta limits, server-rendered JSON-LD verified from raw HTML, sitemaps built from data rather than a hand-kept list, internal links that actually resolve, and the entity rules that stop `&amp;` rendering literally in a page title. |
| `launch-files` | The files a site launches without: the real favicon (head tags do not replace `/favicon.ico`), `llms.txt`, `robots.txt`, `og:image` — and the rule that each must carry the live domain, never a preview URL. |
| `migration-parity` | Everything on the client's old page has to exist on the page replacing it. Compares headings, body text, phone numbers, email addresses, forms, images, alt text and links, one by one, and refuses to pass a page it could not actually read. |
| `study-reference` | Reads a reference page's real numbers instead of an impression of them: type scale, colour, spacing, section rhythm, every transition and animation with its duration and easing, what changes on hover, what animates in on scroll and how far it travels, and whether any of it is switched off for reduced motion. |
| `ai-image-direction` | Photography that reads as real: the phrases to always include, the negative prompt, and the list of images never to generate at all. |

### Routes

| Skill | When |
|---|---|
| `build-route` | Decide from evidence which route the work takes, never from a similar project |
| `lovable-prompting` | Read the project through its MCP first (reading is free), then one narrow prompt that ends with a stop instruction, so the agent does not burn credits verifying |
| `wordpress-work` | Pull before you upload, read every save back, bypass the cache before believing anything, and watch for the en dash WordPress inserts on its own |
| `demo-site-pitch` | A mockup to win the work: why a template loses the pitch, the MIT-only stack, a per-project deploy key, and the pre-flight before it goes to the client |
| `custom-mcp` | How a per-site MCP is built, secured and kept honest |

### Knowledge

| Skill | What it keeps |
|---|---|
| `site-recon` | Everything discoverable about a client's existing site, and the short list of what genuinely has to come from them |
| `client-log` | A dated, append-only record of everything the client gave or said, with the files filed beside it |
| `client-content-audit` | What arrived, what is thin, what is truncated, and what to refuse to publish |
| `forms-and-leads` | The silent failure modes, and the hard line on where a lead's data may never go |

---

## The agent

`site-recon` is a read-only discovery agent. Give it a domain and it works out
the registrar, who really owns the name, which DNS zone is actually being
served, the hosting, the platform, the mail records, the brand assets and the
contact details.

It asks **two independent resolvers** for every DNS answer and flags any
disagreement, because that disagreement is the signal that a hosting control
panel is showing a zone that is not the live one. Editing the wrong zone and
reporting success is a mistake it exists to prevent.

It hands back three sections and nothing else: **facts** with how each was
checked, **risks** including what must survive a change, and **what still has
to come from the client** — never asking for something already in the facts.

---

## The tools

Each one is small, does one thing, and reports measurements rather than
impressions.

| Tool | What it does |
|---|---|
| `job.py` | The job runner: holds state in the client's own folder, runs every check in parallel, diffs after against before, and will not close a launch over a standing blocker |
| `rqa.js` | Responsive QA across six viewports, with screenshots and a findings report |
| `study.js` | Measures a reference page into a spec you can build to, and measures your own build the same way so the comparison is numbers against numbers |
| `parity.py` | Old page against new, element by element, with the main-content coverage figure that nav and footer cannot inflate |
| `recon.py` | Domain, DNS from two resolvers, registrar via RDAP, hosting, TLS, platform, analytics, brand assets. No API keys. |
| `ogcard.py` | Builds a 1200x630 share card from a photo the site already owns, with a gradient scrim so the logo stays readable, under a size budget |
| `check.py` | favicon, `robots.txt`, `llms.txt`, sitemap and `og:image` across any number of domains |
| `preflight.py` | Before a demo goes to GitHub: secrets, `.gitignore`, dashes in visible content, clean tree, and that the production build passes |
| `clog.py` | Add to and search the client log |
| `install.py` | Sync skills and agents to where Claude Code loads them, checksum verified |
| `leakcheck.py` | Reads the client names off the machine and refuses to let any of them into this repository |
| `gatetest.py` | 35 cases proving the claim gate fires exactly when it should and never otherwise |

---

## The principles

Every one of these came from something that actually went wrong.

1. **Test three or four different ways, not the same way three times.** Code,
   live DOM, and the data layer — not the same request repeated.
2. **Look at it, every time.** Screenshot at phone and desktop width and read
   it. A page can pass every technical check and still be visibly broken, so
   reading the code or the DOM is not looking. This one is enforced.
3. **Distrust a single green result**, especially a cached one. Check the build
   hash before believing a deploy.
4. **Distrust any agent's self-report.** A build tool saying "done" is a claim
   to verify, not a fact.
5. **A 403 is not "the site is down."** It may be blocking you specifically
   while serving everyone else normally. Check another way before saying it.
6. **Say plainly what is fact, what is inference, and what could not be
   checked.** An honest gap is useful; a plausible guess is how an account is
   lost.
7. **Never invent a licence number, a certification, a review count or a
   statistic.** On regulated work that is a liability, not a cosmetic slip.
8. **Change only what was asked**, and prove nothing else moved.

---

## Publishing safely

This repository is deliberately free of client identity. `leakcheck.py` reads
the client folder names and their live domains off the machine, then scans
every file here for them, along with credentials, private keys, public IP
addresses, personal paths and email addresses. It exits non-zero on anything it
finds.

```bash
python leakcheck.py
```

Run it before every push. The skills describe what was learned, never from
whom.

---

## Using it

```bash
python install.py --apply     # sync skills and agents, checksum verified
python install.py --status    # what is installed, and whether it has drifted
```

Skills load at session start and fire on their own from the words in a request.
Most of the time nothing has to be invoked by name.

---

## The gate

Skills are advice until something enforces them. A `Stop` hook reads the turn
that just finished. If the reply claims the work is done, files were changed,
and nothing in that same turn went and looked, the turn is blocked and sent
back to verify, with a reason naming what counts as proof for that kind of
claim.

There is a second, stricter tier for anything a person judges with their eyes.
If the turn changed a UI file, or the reply claims something about a page,
hero, header, button, layout, colour, font or animation, **a screenshot is the
only evidence that counts**. A passing build, a green curl and a clean
`git diff` do not clear it, because a page can pass every technical check and
still be visibly broken.

It blocks at most once per turn, so it cannot loop. A reply that is honest
about not having checked is never blocked, and neither is a turn that changed
nothing. `gatetest.py` covers all 35 cases, including the Hinglish phrasings
this workspace actually uses.

```bash
python install.py --gate off     # and --gate on
```

The hook is the floor, not the standard. It can only see that *something* was
checked. Whether the right thing was checked is still a judgement, and that is
what the skill is for.

## Status

In daily use: 22 skills, one agent, twelve tools and four hooks — session start,
the context recorder, a guard on writes that land outside the project, and the
claim gate.

Test suites: 35 gate cases, 49 fix-job cases, 22 migration-parity cases, 11 ogcard
cases, 38 study-reference
cases, 27 context-system cases, a full-file verifier and a leak check, all
passing.
