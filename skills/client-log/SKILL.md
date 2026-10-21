---
name: client-log
description: Keep a dated record of everything the client gives or says — files, images, briefs, instructions, decisions, approvals and complaints — filed in the project so it can be found months later when something is disputed. Use the moment the user mentions that a client sent, said, asked for, approved or changed something. Triggers on "client ne ye file di", "client ne bola", "client ne bheja", "client said", "client sent", "client approved", "client wants", "ye image client ne di hai", "client ka brief", or any sentence where the client is the source.
---

# The client log

When a client says "but I told you Y" six weeks later, there are two possible
answers. One is a dated line with the file attached. The other costs the
account.

This is append-only. Never rewrite an entry; add a new one that supersedes it.

## Record it the moment it is mentioned

As soon as the user says a client gave or said something, log it. Do not wait
until the end of the task, and do not ask whether it is worth logging.

```bash
python "C:\Claude-Code\.ai-system\skills\client-log\clog.py" add "<Project>" ^
  --what "<one line: what arrived or was said>" ^
  --from "<who>" --via email|whatsapp|call|upwork|lovable|meeting ^
  --kind ask|decision|asset|approval|complaint|info ^
  --date YYYY-MM-DD ^
  --note "<what it means, in your words>" ^
  --files <paths...>
```

Files are **copied**, never moved, into
`<project>\.claude-context\client-log\<date>-<slug>\` and verified by checksum.
The ledger is `<project>\.claude-context\CLIENT-LOG.md`.

Finding it again:

```bash
clog.py search "<Project>" blue logo      # entries containing all the terms
clog.py list "<Project>" --open           # what is still open
```

## What to capture

| Kind | Example |
|---|---|
| `asset` | logo files, photos, a content pack, a CSV of their data, brand guidelines |
| `ask` | "can we add a booking form", a correction list, a feature request |
| `decision` | "no blue anywhere", "drop the Spanish pages", "use Indeed for applications" |
| `approval` | sign-off on a page, a design, a go-live |
| `complaint` | "the stats do not match my database", "it looks broken on my phone" |
| `info` | a password location, an account they own, a deadline, a constraint |

Always record **where it came from** (email, WhatsApp, a call, the Lovable
chat, Upwork) and **the date they said it**, not the date you logged it.

## Write the note so it is useful in six months

Not "client sent feedback". Write what it actually means and what it changes:

> He was clear that blue reads cold for a water-damage brand. Greens and warm
> neutrals only. This overrides the palette in the 12 Sep mockup.

Say explicitly when an entry supersedes an earlier one, and name the earlier
date. Contradictions between client instructions are normal; losing track of
which came last is what causes rework.

## An entry is a record of what was ASKED

It is **not** evidence that anything was delivered. A line saying "client asked
for X" and a later line saying "X was built" are two different claims, and the
second one still has to be verified against the live site before anyone tells
the client it is done. See `verify-before-claiming` and `client-reply`.

When something is genuinely finished and checked, add a new entry that closes
the loop, with how it was verified.

## Things that must not go in the log

- **Passwords, API keys, tokens.** Record where the credential lives ("team
  password manager", "visible in the SiteControl panel"), never the value.
- Anything the client marked confidential that is not needed for the work.

## Relationship to memory

The log is the chronology: everything, in order, with the files. Memory is the
distilled version: the handful of standing facts and rules worth loading every
session.

When an entry establishes a **standing rule** ("the hero must fit the screen on
every landing page", "never change the BCC address"), also write it to
`.claude-context\memory\` so it is active, not just archived. The log explains
where the rule came from; memory makes it apply.

## At the start of a task

Read `CLIENT-LOG.md` before building anything on an existing project. It
answers the two questions that cause the most rework: what did they already ask
for, and what have they already decided against.
