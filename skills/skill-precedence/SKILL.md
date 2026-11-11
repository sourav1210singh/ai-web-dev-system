---
name: skill-precedence
description: What to do when two skills both apply. One that knows how a particular system is operated, and one that sets what good work is. Use whenever an account-level or client-specific skill fires alongside these standards, when two skills give different instructions, or when a pipeline skill would produce something the standards forbid. Triggers on two skills matching one request, a skill that conflicts with a standard, "which skill", "dono me se kaun sa", or any pipeline skill that ends by claiming work is done.
---

# When two skills both apply

Skills arrive from two places and they are not the same kind of thing.

**Executors** know how a particular system is operated. Which portal, which
sheet, which editor, what order the buttons go in, what that client's own
rules are. They are usually specific to one site, one agency process or one
tool, and they are usually synced to an account rather than kept on disk.

**Standards** (this set) say what good work is and what may be claimed about
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
  tracking sheet, a task marked complete, a tool reporting success. All of
  these are claims to verify. See `verify-before-claiming`.

## What the standards never override

- The order of operations inside someone else's portal.
- Which account, sheet, folder or property a client's work belongs in.
- A client's own stated preference about their own content.
- Rate limits, daily caps and posting rules. An executor that says "twenty a
  day" knows something these skills do not.

## The account skills that cover the same ground

These pairs fire on the same request. The executor runs the process; the
standard beside it still decides what may be claimed and what good looks like.

| Account skill | House skill | Who decides what |
|---|---|---|
| `lovable-credit-discipline` | `lovable-prompting` | either may write the prompt; the house rule that **nothing is sent without the user pressing enter** is not theirs to relax |
| `screaming-frog-seo`, `ahrefs-recommendation`, `wp-seo-implementor` | `seo-complete` | they run the crawl and the report; the house limits on titles, meta, schema and redirects decide what gets changed |
| `wp-page-builder` | `wordpress-work` | it knows the editor; the house rules on pulling before uploading, the saves that do not save and the caches that hide a change still apply |
| `stop-slop`, `content-writer` | `copy-standards` | they draft; the house bans on dashes, filler and invented facts are absolute |
| `competitor-gap-analysis` | `study-reference` | it gathers; a claim about how a competitor's page behaves still needs the page measured, not described |
| `skill-creator` | this skill | see below |

## A new skill is a last resort

`skill-creator` will happily make a new skill out of any instruction. Most
instructions are not new subjects.

> **Find the skill that already owns that ground and edit it.** Create a new
> one only when nothing covers the subject at all.

Two skills that half-cover one subject route worse than one that covers it
fully, and the knowledge splits: the rule ends up in one file and the trap
that proves it in another, so whichever one fires is missing half the reason.
This has already happened once here: a rule about looking at a file before
describing it was written as its own skill when `verify-before-claiming`
already had a section called "Looking at it is not optional". It was folded
back in.

Before writing a new `SKILL.md`, name the closest existing skill out loud. If
a new one is created anyway, say in one line why no existing skill fitted. The
same goes for hooks, scripts and agents.

## When they genuinely conflict

Say so in the reply, in one line: which two skills, what each wanted, which
one you followed and why. Do not silently pick. A conflict that keeps
recurring is a skill that needs editing, and it will never get edited if it is
only ever resolved quietly.

## A skill that lives only on an account

It is one login away from gone. Anything worth keeping belongs on disk, in the
project, where it survives a switch, and anything worth keeping *permanently*
belongs in this system with the client's details stripped out, so it survives
the next machine as well.

Before moving a client-specific skill into a published system, run the leak
check. Client names, domains, project IDs and logins travel inside skill text
far more often than anyone expects.
