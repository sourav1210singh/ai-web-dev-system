---
name: fix-job
description: Run client site work end to end as a job with state, in five types: fix (something live is wrong), intake (a new client, read everything, change nothing), golive (the launch gate, nothing ships with a blocker standing), drop (rankings or traffic fell: diagnose before changing anything, and check for a manual penalty before concluding it was an algorithm) and watch (a site that is already live: run it weekly and it reports only what changed, including a form that has quietly disappeared or a page that has doubled in weight). Every check runs at once, the job stops at the human gate, and verify diffs against the before state. Use when a client reports a problem, when a new client arrives, before any launch, or when picking up work left half done. Triggers on "fix karo", "ye issue hai", "client ne bola hai", "form kaam nahi kar raha", "naya client", "new client", "intake", "go live", "launch", "live karna hai", "job", "resume", "watch", "traffic down", "traffic gir gaya", "ranking gir gayi", "penalty", "algorithm update", "organic drop", "leads kam ho gaye", "monitor karo", "sab theek chal raha hai", "leads aa rahe hain", "weekly check". It owns "go live": the launch gate runs site-recon, migration-parity, responsive-qa, launch-files and security-pass as its checks, so those do not need calling separately.
---

# Client work, run as a job

Three types, one runner. They differ in what they check, whether they stop at
a gate, and what they refuse to do.

| Type | For | Gate | Refuses |
|---|---|---|---|
| `fix` | something live is wrong | yes | nothing, but verify fails on a regression |
| `intake` | a new client, before touching anything | no | it changes nothing at all |
| `golive` | the launch gate | yes | to close while a blocker stands |
| `watch` | a site that is already live, run again weekly | no | nothing; it reports only what changed |

```bash
python job.py new "<name>" --domain <d> --dir "<project>" --type intake
```

## intake: read everything, change nothing

For a new client or a takeover. Runs recon, launch files and responsive QA
together, and reports what the domain says about itself: registrar,
nameservers, the DNS actually being served, hosting, platform, mail records,
TLS, analytics.

It has **no apply stage and no gate**, because an intake that changes
something is not an intake. It ends at `report`, where you write the three
things that matter: the facts with how each was checked, the risks including
what must survive a change, and the short list of what genuinely has to come
from the client. See `site-recon` for what that report should contain.

## watch: after it is live, which is where most of the risk is

Every other type ends at handover, and a job that ends at handover is a job
that finds out from the client. Run this one again on the same id, weekly, and
it reports **only what changed** since last time:

```bash
python job.py new "<client> watch" --domain <d> --dir "<project>" --type watch
python job.py watch <id> --dir "<project>"      # and again next week
```

The first run is a baseline and says so. Every run after it prints `GONE` for
anything that was a problem and no longer is, and `NEW` for anything that was
not a problem and now is. Nothing else. A full audit every week is a thing
nobody reads; four lines saying what is different gets read.

It runs the launch files, responsive QA, the load pass and the accessibility
pass, and it records two things even when they are fine, because the change is
the finding:

- **page weight and request count.** A threshold catches a page that is too
  heavy. Nothing but a comparison catches a page that doubled.
- **how many forms, submit buttons, mailto and tel links there are.** On one
  site the endpoint, the table and the mailer were all healthy for two months
  after the forms had been replaced with links to an off-site page, and nobody
  found out until the client asked where the leads had gone. A watch sees
  `1 form(s)` become `0 form(s)` the week it happens.

"Nothing has changed since the last run" is a real answer and worth sending to
the client as plainly as a list of problems would be.

### Make it run without being remembered

A weekly check that needs a person to remember it is not a weekly check. The
form that quietly disappeared was found when the client asked where the leads
had gone, and that is exactly what a schedule exists to prevent.

```bash
python "C:\Claude-Code\.ai-system\skills\fix-job\watchrun.py" --dry-run
python "C:\Claude-Code\.ai-system\skills\fix-job\watchrun.py" --status
python "C:\Claude-Code\.ai-system\skills\fix-job\watchrun.py" --schedule
```

`watchrun.py` finds every open watch job in every project, runs them, writes
one summary a person reads into `.context-system\watch\`, and records the run.
It exits non-zero when something moved, so a scheduler's own failure mail
becomes the signal.

**It will not register the scheduled task itself.** That changes the machine's
configuration, which is the user's to do. `--schedule` prints the exact
`schtasks` command; run it yourself, then confirm with `--status`.

**`--status` is the part worth running often.** It reads whether the task is
actually registered and when the run last happened, and says so plainly:

- never run, and no task registered
- last ran more than ten days ago, because **a schedule that stopped looks
  exactly like a set of sites with no problems**, which is why staleness is
  reported as loudly as a finding
- no open watch jobs at all, which is itself worth knowing if those sites are
  live

A session that is about to tell someone the sites are healthy should check this
first. "No problems reported" and "nothing has been checked for a month" read
identically in a job file and mean opposite things.

## golive: the launch gate

Runs what `fix` runs, plus the security pass, and **close refuses while a
blocker is standing** and exits non-zero. A launch gate that waves things
through is not a gate.

What holds a launch is deliberately narrow: no https, an invalid certificate,
active mixed content, a form posting in the clear, a readable `.env`, a key
shipped into the bundle, and no way back. A missing Content-Security-Policy is
reported and does not hold the launch. A gate that refuses to open for the
normal state of the web is a gate people learn to force.

### The way back

```bash
python "C:\Claude-Code\.ai-system\skills\fix-job\rollback.py" <project> --build
python "C:\Claude-Code\.ai-system\skills\fix-job\rollback.py" <project>
```

`--build` writes `<project>\.claude-context\rollback.json`, filling in what the
recon output already knows: the records about to change, the mail records that
must survive, the nameservers, the host, the TTL, and leaving the fields only
a person can answer **empty and named**, because an empty field is a question
and a guessed one is a false answer.

Running it without `--build` checks the plan, and the checking is the point.
Every launch has a rollback plan in the sense that somebody will say "we can
just point it back". That sentence is not a plan:

| What it refuses | Why |
|---|---|
| No backup named | "Restore from backup" with no path is the commonest fake plan there is, and it is discovered at the worst possible moment. |
| A backup that is not at the path given | Worse than no plan, because it is believed. |
| Mail records not recorded | Putting the site records back does not bring mail back if the MX records were replaced too. `site-recon` is blunt about this one: it is the one that loses a client. |
| The old origin already gone | Old hosting gets cancelled on launch day by someone being tidy, and then there is nothing to go back to. |
| Never verified | A plan nobody has tested is a sentence. `verified_on` means somebody opened the backup and confirmed the old host answers. |

Reported but **not** blocking: a long TTL, no named trigger, nobody named to
execute it, a plan last verified more than two weeks ago.

Two details worth keeping:

- **A domain with no mail is not blocked for having no MX records.** The recon
  pass records whether it found any mail at all, and a preview host or a domain
  whose mail lives elsewhere gets a note asking you to confirm, not a blocker.
  A gate that blocks every such launch forever is a gate forced open by habit.
- **Lower the TTL before the launch, not just before the revert.** Resolvers
  already holding the old value keep it for its full term, so dropping the TTL
  an hour before a change buys nothing. It has to be done at least one old-TTL
  period in advance. The TTL figures a resolver reports are the time left on
  its cached copy, so they are lower bounds. Read the zone's own value in the
  DNS panel before promising anyone a revert window.

If it ships anyway, that is a decision someone makes, not a check that is
skipped. `--force` closes it and writes `CLOSED OVER STANDING BLOCKERS` into
the job history, so the record says it was chosen rather than missed.

## drop: why has traffic fallen

A diagnosis, not a fix. It changes nothing and ends with a prioritised plan.

```bash
python job.py new "Drop analysis" --domain <domain> --type drop
```

### Check for a manual action before concluding anything

This is the order, and getting it wrong costs weeks. **A manual penalty and an
algorithmic drop have completely different remedies.** One is a reconsideration
request after fixing a named violation; the other is quality work with no
switch to flip. Open Search Console and read Manual Actions and Security Issues
first, and write down what it said, including "no issues detected", because
that is the finding that makes the rest of the analysis mean something.

### Quantify it, then date it

- Peak clicks and the month they happened, current clicks over the last 28
  days, and the decline worked out explicitly: `(peak - current) / peak * 100`.
- **Which month the fall started**, not "a few months ago".
- The five pages and five keywords that lost most, with before and after
  positions.
- Then cross-reference that month against Google's update history. **Fetch the
  current list** from `developers.google.com/search/updates/core-updates` - do
  not work from a remembered table of update dates, which goes stale and takes
  the conclusion with it.

**Flag the double hit.** If a migration and an algorithm update land in the
same month, say so plainly instead of picking one. Attribution is genuinely
ambiguous then, and the recovery timeline is longer. Pretending to know which
it was is the most expensive thing you can write in that report.

**The archive shows when Google saw a change, not when it shipped.** Confirm
the deploy date with the client before building a timeline on it.

### What the Search Console indexing report is telling you

Each bucket means something different, and the counts are the evidence:

| Bucket | What it points at |
|---|---|
| Soft 404 | A migration whose old URLs were never redirected. A URL that answers 200 and says "not found" is the single clearest fingerprint of this, and `seo.js` detects it directly. |
| Crawled, currently not indexed | Content quality. Google fetched it and decided against it. |
| Discovered, currently not indexed | Crawl budget, usually too many low-value URLs. |
| Duplicate without canonical | The four address variants, or a parameter explosion. |
| Excluded by noindex | A staging flag that survived a launch, until proven otherwise. |

### What this job measures, and what it cannot

It runs recon, the launch files, the SEO pass and the security pass, so it
reaches: soft 404s, robots and sitemap faults, noindex, broken internal links,
thin and keyword-stuffed pages, hidden text linking off-site, a compromised
site, and whether the hosting or DNS moved.

**It cannot see Search Console.** The traffic numbers, the manual action, the
indexing buckets and the keyword losses are all read by a person or a
connector, and they are the half that says *when* and *how much*. The pass
tells you what is wrong with the site; it does not tell you that traffic fell.
Do not write a drop report from the crawl alone.

Core Web Vitals are not a usual cause of a ranking collapse. Check them, after
the rest, and do not lead with them.

### Order the plan by impact, not by effort

| When | What belongs there |
|---|---|
| 24 to 48 hours | Hacked pages still indexed, a manual penalty, robots.txt blocking Googlebot, mass soft 404s from missing redirects |
| Week 1 to 2 | Individual soft 404s, crawled-not-indexed at scale, the missing old-to-new redirect map, a sitemap full of 404s and redirects, noindex on pages that should rank |
| Week 3 to 5 | Missing schema, weak expertise signals, thin or stale content, orphan pages, meta quality |
| Ongoing | Content depth, link recovery, Core Web Vitals, the business profile |

A ten-minute fix that stops a spam signal still goes in the first week.

## fix: one fix, end to end

A fix is not one action. It is: work out where the site lives, read what is
actually there, measure what is wrong, make the change, wait for the person
who presses the button, prove the change landed, prove nothing else moved,
tell the client. Done one prompt at a time, steps get skipped. Run as a job,
the state survives and nothing is forgotten.

```bash
python "C:\Claude-Code\.ai-system\skills\fix-job\job.py" new "<name>" --domain <d> --dir "<project folder>"
```

The job file lives in that client's own `.claude-context/jobs/`, so it belongs
to the project and survives this session, this account and this machine.

## The six stages

| Stage | Who | What happens |
|---|---|---|
| route | Claude | Which of the three routes, from evidence. Never from a similar project. `site-recon` or `recon.py` if it is not already known. |
| read | Claude | Open the real files. Lovable through its MCP, WordPress through the admin the user opened, a direct build from disk. Reading is free; assuming is not. |
| diagnose | tool | `job.py diagnose <id>` runs launch files, responsive QA and content parity **at the same time** and saves the result as the before state. |
| apply | **the user** | The gate. See below. |
| verify | tool + Claude | `job.py verify <id>` re-runs everything and diffs it against before. Then Claude reads the screenshots. |
| close | Claude | `job.py close <id>`, then the client log entry and the reply. |

## The gate is the point of this skill

**Lovable:** write the prompt to a file in the project, then
`job.py gate <id> --awaiting user-paste --note "<file>"`. Claude does not send
it. The user pastes it and presses enter. See `lovable-prompting`.

**WordPress:** the user signs in on their own profile. Claude works inside the
session they opened, reads everything the task touches before changing
anything, and never enters a credential. See `wordpress-work`.

**Direct build:** no gate. Claude does the work.

When the user says their part is done: `job.py resume <id>`. The job picks up
at verify with the before state still on disk, so nothing has to be explained
again.

## Verify means two different things, and you owe both

`job.py verify` gives you the measured half: what is fixed, what is new. A
**NEW** line means the change broke something that was fine before, and the
command exits non-zero. Do not close on that.

The other half is yours. Open the screenshots it wrote and look at them. A
page can pass every check and still be visibly broken. The claim gate enforces
this and will not accept a build log in place of an eye. See
`verify-before-claiming`.

## Why diagnose runs everything at once

The checks are independent and each takes a while. Run serially they cost
several minutes of waiting and encourage skipping the slow one. Run together
they cost the slowest. There is no reason to look at only part of a site when
the whole measurement is this cheap.

Four at a time, not all of them: a `watch` has six checks and five of them
launch a browser, so the cap is there to keep the machine usable rather than
because the work is ordered.

The before snapshot also settles the argument that costs the most time later:
*was that already broken, or did we break it?* Without a before state, that is
a matter of opinion.

## Never try this out on a client's site

A client domain is not a test target, and that includes read-only runs. Do not
pick one to prove a tool works. Ask for a site that is safe to point at, and
until there is one, test against fixtures, a saved HTML file, or a neutral
public page that belongs to nobody here.

This matters more than it looks. A diagnostic run leaves entries in the
client's analytics, can trip a WAF, and above all sets the habit of reaching
for a live site when something needs checking.

## When a job cannot continue

Say so in the reply and leave the job at its stage. A job parked at `apply`
waiting on the client's DNS is a true record. A job marked closed because the
conversation ended is a lie that someone finds in three months.

`job.py status` lists every open job in a project, with what each is waiting
for.
