---
name: demo-site-pitch
description: Build a demo or mockup site to win a client, push it to GitHub with a per-project deploy key, deploy it to Vercel and send the client a link. Covers why a pre-made template loses the pitch, the MIT-only stack, the multi-GitHub-account SSH setup, the pre-flight before pushing, and the honesty rules that keep a pitch credible. Use when a client wants a demo, mockup, sample or pitch site, for an Upwork proposal, or when asked to deploy something for client review. Triggers on "demo website", "mockup", "pitch", "sample site", "client ko dikhana hai", "vercel", "github pe daalo", "deploy", "preview link".
---

# Demo site for a pitch

The job is to win the work. The site has to look custom-built, load fast on a
phone, and say nothing that cannot be backed up.

## Do not start from a template

This was decided with evidence on a real pitch, not as a preference:

- **The single biggest tell of an AI-built site is an untouched template.**
  Recognisable layout, default fonts, stock photos, generic copy. Reviewers
  spot it instantly.
- Component catalogues like 21st.dev carry **no local-service or contractor
  templates** — they are SaaS landing pages, AI products, dashboards, crypto
  and portfolios. And their house aesthetic (dark gradient heroes, glowing
  orbs, glassmorphism, animated beams) is exactly the "AI startup" look to
  avoid. On a trades site it reads as fake.
- The free tier is 2 component copies a day, so building five pages that way
  takes weeks or money.
- Templates optimise for impressing a scrolling browser. A pitch site usually
  has a different job, and they fight it with heavy hero animation, carousels
  and scroll-jacking.
- Exact control over semantic HTML, heading order, real `<table>` elements and
  JSON-LD is needed for the SEO and answer-engine work, and templates fight you
  on all of it.

The honest trade-off is a day or two more work. For a pitch that has to win a
retainer, that is the right trade. Say so out loud rather than quietly
spending the extra day.

## The stack

Everything MIT, so there is zero licence risk on commercial client work:

```
Next.js (App Router) + TypeScript   static generation, SEO control, native Vercel deploy
Tailwind CSS                        full design control, no CSS bloat
shadcn/ui                           accessible primitives copied into the repo, not a theme
motion                              restrained micro-interactions only
lenis                               smooth scroll
lucide-react                        icons, never generated image icons
```

`web-build-standards` applies in full. `ai-image-direction` governs any
photography.

## Research before design

Both demo projects here began with a `research/` folder and a `PROJECT-PLAN.md`
before a line was written: competitor analysis, and an SEO/answer-engine
strategy.

That research is what makes the pitch credible, and it often shows the brief is
partly wrong. On one pitch the client's brief assumed AI Overviews on
transactional queries; the research found the Local Pack owns those, and that
no location-specific cost content existed anywhere in that market. Saying that,
with evidence, and building the page that fills the gap is what turns a mockup
into an argument.

Write the plan first and let the user read it: the deliverable, the template
decision with reasons, the stack table, and the honest trade-off.

## Honesty rules for a pitch

A mockup is still published work with the client's name on it.

**Never put on the page:** licence numbers, certifications, review counts,
response-time promises, years in business, or awards the client has not
confirmed. On one trades pitch this was a real liability: the state requires
a contractor licence for that work and insurers require a specific
certification, so inventing either is not a cosmetic mistake.

**Never promise an outcome** in the site copy or the proposal. Commit to the
method and the diagnosis.

Use clearly marked placeholders instead, and list them for the client. See
`copy-standards` and `client-content-audit`.

## Pre-flight before pushing

```bash
python "C:\Claude-Code\.ai-system\skills\demo-site-pitch\preflight.py" <project-dir>
```

Checks `.gitignore` covers `node_modules` and `.env`, looks for anything that
smells like a committed secret, finds em and en dashes **in visible content**
(ignoring code comments) and prints the offending line, confirms the working
tree is clean and that the production build passes, then prints the exact
commands for this project with the names filled in. It changes nothing.

Run `responsive-qa` on every page before the link goes out.

## GitHub with more than one account

Plain `git@github.com:` picks whichever key SSH offers first, which on a
machine with several GitHub identities is the wrong one. Use a **per-project
alias and a dedicated deploy key**:

```bash
ssh-keygen -t ed25519 -C "<project> deploy" -f ~/.ssh/<project>_deploy
```

Add the `.pub` as a **Deploy Key with write access** on that repo, not to the
personal account, then in `~/.ssh/config`:

```
Host github-<project>
  HostName github.com
  User git
  IdentityFile ~/.ssh/<project>_deploy
  IdentitiesOnly yes
```

`IdentitiesOnly yes` is the part that matters; without it SSH still offers
every other key first.

```bash
ssh -T git@github-<project>        # must greet the right account
git remote add origin git@github-<project>:<user>/<repo>.git
git push -u origin main
```

Commit messages in plain English, saying what changed: "Remove every em dash
from the site", "Flip the services card from dark to light".

## Vercel

Connect the repo from the Vercel dashboard: **Add New > Project > Import from
GitHub**. A standard Next.js app needs no settings; the framework is detected.
Every push to `main` redeploys, and every branch gets its own preview URL.

Do not commit a `.env` to make the build work. Put the values in Vercel's
Environment Variables.

**Before sending the link:**

1. Open the Vercel URL itself, not localhost
2. Run `responsive-qa` against that URL
3. Check `launch-files`: favicon, og:image on the real host, robots, sitemap
4. Click every nav link and every CTA
5. Submit any form and confirm where it goes, or say plainly that forms are not
   wired up in the demo

**Then record it**, or it is lost: put the Vercel URL and the repo in the
project's memory, and log the send with `client-log`. One plan in this
workspace says "deploy to Vercel for client review" and no URL was ever
written down.

## Sending it

Short, plain English, no markdown, nothing claimed that was not checked. Say
what is real and what is a placeholder. See `client-reply`.
