---
name: fix-job
description: Run client site work end to end as a job with state, in four types - fix (something live is wrong), intake (a new client, read everything, change nothing), golive (the launch gate, nothing ships with a blocker standing) and watch (a site that is already live: run it weekly and it reports only what changed, including a form that has quietly disappeared or a page that has doubled in weight). Every check runs at once, the job stops at the human gate, and verify diffs against the before state. Use when a client reports a problem, when a new client arrives, before any launch, or when picking up work left half done. Triggers on "fix karo", "ye issue hai", "client ne bola hai", "form kaam nahi kar raha", "naya client", "new client", "intake", "go live", "launch", "live karna hai", "job", "resume", "watch", "monitor karo", "sab theek chal raha hai", "leads aa rahe hain", "weekly check". It owns "go live": the launch gate runs site-recon, migration-parity, responsive-qa, launch-files and security-pass as its checks, so those do not need calling separately.
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

## intake - read everything, change nothing

For a new client or a takeover. Runs recon, launch files and responsive QA
together, and reports what the domain says about itself: registrar,
nameservers, the DNS actually being served, hosting, platform, mail records,
TLS, analytics.

It has **no apply stage and no gate**, because an intake that changes
something is not an intake. It ends at `report`, where you write the three
things that matter: the facts with how each was checked, the risks including
what must survive a change, and the short list of what genuinely has to come
from the client. See `site-recon` for what that report should contain.

## watch - after it is live, which is where most of the risk is

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

## golive - the launch gate

Runs what `fix` runs, plus the security pass, and **close refuses while a
blocker is standing** and exits non-zero. A launch gate that waves things
through is not a gate.

What holds a launch is deliberately narrow: no https, an invalid certificate,
active mixed content, a form posting in the clear, a readable `.env`, a key
shipped into the bundle. A missing Content-Security-Policy is reported and does
not hold the launch - a gate that refuses to open for the normal state of the
web is a gate people learn to force.

If it ships anyway, that is a decision someone makes, not a check that is
skipped. `--force` closes it and writes `CLOSED OVER STANDING BLOCKERS` into
the job history, so the record says it was chosen rather than missed.

## fix - one fix, end to end

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
