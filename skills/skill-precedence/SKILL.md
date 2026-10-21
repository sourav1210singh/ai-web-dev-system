---
name: skill-precedence
description: What to do when two skills both apply - one that knows how a particular system is operated, and one that sets what good work is. Use whenever an account-level or client-specific skill fires alongside these standards, when two skills give different instructions, or when a pipeline skill would produce something the standards forbid. Triggers on two skills matching one request, a skill that conflicts with a standard, "which skill", "dono me se kaun sa", or any pipeline skill that ends by claiming work is done.
---

# When two skills both apply

Skills arrive from two places and they are not the same kind of thing.

**Executors** know how a particular system is operated. Which portal, which
sheet, which editor, what order the buttons go in, what that client's own
rules are. They are usually specific to one site, one agency process or one
tool, and they are usually synced to an account rather than kept on disk.

**Standards** — this set — say what good work is and what may be claimed about
it. They are not about any one system.

Both apply at the same time. The standard does not lose because the executor
was more specific about the task.

## The rule

> The executor decides **how this system is operated**.
> The standard decides **what good work is and what may be claimed**.
> Where they disagree about quality, truthfulness or scope, the standard wins.
> Where they disagree about which button to click, the executor wins.

## What never yields, whatever an executor says

- **A visual claim needs a screenshot, read.** The claim gate enforces this
  and there is no executor-specific exemption. A pipeline that ends "published
  successfully" has still not looked at the page.
- **Nothing invented.** No statistic, licence number, certification, review
  count or qualification that was not supplied. A content pipeline under
  deadline is exactly where this slips, and on regulated work it is a
  liability rather than a cosmetic one.
- **No em dashes or en dashes, no AI filler.** An executor that writes prose
  does not get its own vocabulary rules.
- **Only what was asked changes.** A builder skill that "improves while it is
  in there" is a regression generator. Capture before, diff after.
- **A record of an action is not evidence of an outcome.** A row written to a
  tracking sheet, a task marked complete, a tool reporting success — all of
  these are claims to verify. See `verify-before-claiming`.

## What the standards never override

- The order of operations inside someone else's portal.
- Which account, sheet, folder or property a client's work belongs in.
- A client's own stated preference about their own content.
- Rate limits, daily caps and posting rules. An executor that says "twenty a
  day" knows something these skills do not.

## When they genuinely conflict

Say so in the reply, in one line: which two skills, what each wanted, which
one you followed and why. Do not silently pick. A conflict that keeps
recurring is a skill that needs editing, and it will never get edited if it is
only ever resolved quietly.

## A skill that lives only on an account

It is one login away from gone. Anything worth keeping belongs on disk, in the
project, where it survives a switch — and anything worth keeping *permanently*
belongs in this system with the client's details stripped out, so it survives
the next machine as well.

Before moving a client-specific skill into a published system, run the leak
check. Client names, domains, project IDs and logins travel inside skill text
far more often than anyone expects.
