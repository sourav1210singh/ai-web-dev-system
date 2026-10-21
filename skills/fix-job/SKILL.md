---
name: fix-job
description: Run client site work end to end as a job with state, in three types - fix (something live is wrong), intake (a new client, read everything, change nothing) and golive (the launch gate, nothing ships with a blocker standing). Every check runs at once, the job stops at the human gate, and verify diffs against the before state. Use when a client reports a problem, when a new client arrives, before any launch, or when picking up work left half done. Triggers on "fix karo", "ye issue hai", "client ne bola hai", "form kaam nahi kar raha", "naya client", "new client", "intake", "go live", "launch", "live karna hai", "job", "resume".
---

# Client work, run as a job

Three types, one runner. They differ in what they check, whether they stop at
a gate, and what they refuse to do.

| Type | For | Gate | Refuses |
|---|---|---|---|
| `fix` | something live is wrong | yes | nothing, but verify fails on a regression |
| `intake` | a new client, before touching anything | no | it changes nothing at all |
| `golive` | the launch gate | yes | to close while a blocker stands |

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

## golive - the launch gate

Runs the same checks as `fix`, but **close refuses while a blocker is
standing** and exits non-zero. A launch gate that waves things through is not
a gate.

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

The three checks are independent and each takes a while. Run serially they
cost several minutes of waiting and encourage skipping the slow one. Run
together they cost the slowest. There is no reason to look at only part of a
site when the whole measurement is this cheap.

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
