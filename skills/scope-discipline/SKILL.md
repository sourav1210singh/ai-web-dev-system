---
name: scope-discipline
description: Change only what was asked, prove nothing else moved, and never re-do work that is already confirmed working. Use before and after any edit to a live client site, any multi-page change, any migration, and any time a previous session already verified something. Triggers on "sirf ye change karo", "baaki mat chhedna", "don't touch", "regression", "kuch aur to nahi toota", or any edit to a site that is already live.
---

# Change only what was asked

Almost every prompt written on these projects carries a list of what must not be
touched. That is not caution, it is experience: the expensive failures here were
not bad edits, they were edits that quietly broke something adjacent.

## Before you touch anything

None of this is quick, and it is not meant to be. `verify-before-claiming`
has the rule on pace: finishing is not the goal, work that is right is.

1. **Find out what is already confirmed working.** Read the project's CONTEXT
   and memory first. A previous session may have verified exactly the thing you
   are about to "improve". Re-doing confirmed work is how regressions get
   introduced.
2. **Capture the before state.** For a page change, save the rendered HTML of
   every affected page. For a data change, save the rows. For a file change,
   note the checksum.
3. **Write down the blast radius** — the files, routes, tables and components
   this edit can reach — and say it back before starting on anything live.

## While working

- Touch only what the task names. If something adjacent is clearly broken, say
  so and ask; do not fix it in the same change.
- Do not "improve" layout, reorder sections, rename things, reformat files or
  upgrade dependencies that were not part of the ask.
- Do not null fields you were not given. On an update, write only the fields
  that were passed — a missing field must never overwrite a stored value with
  empty.
- Do not change identifiers that other things depend on: slugs, publish dates,
  status, IDs, file paths, route names.

## Write the least code that does it

Scope creep in an AI's hands does not usually look like extra features. It
looks like extra **code**, and that is the single most common thing to correct
in machine-written work.

- **Use what is already there** before adding anything. A helper that almost
  does the job and needs one argument is better than a second helper beside it.
  Read the file first; the function you are about to write is often ten lines
  further down.
- **No abstraction for one caller.** A base class, a config object, a strategy
  map or a `utils/` file introduced for a single use is a cost with no payer.
  Write it inline, and extract it the second time it is needed, not the first.
- **No speculative generality.** Parameters nothing passes, cases nothing hits,
  options nobody set. If it is not needed by this task, it is not needed.
- **No defensive wrapping of things that cannot fail.** A try/except round a
  dictionary literal, a null check on a value the type guarantees, a fallback
  for a branch that cannot be reached. Each one hides the real failure later.
- **Delete as part of the change.** When something is replaced, the thing it
  replaced goes in the same commit. A dead export left behind is what the next
  session reads and believes.

> **Read your own diff before reporting, looking only for what can be
> deleted.** Not for bugs, which is a different pass. The question is: what in
> here is not pulling its weight? That one reading catches more than any review
> checklist, because the author is the only person who knows which lines were
> written out of habit.

The smallest change that fully does the job is the correct change. "Smallest"
is not the same as "quickest": skipping the test or the edge case is not a
smaller change, it is an unfinished one.

## After, before reporting

**Diff the rendered HTML of every affected page against the before capture.
Anything other than a whitespace difference is a regression — fix it before
reporting.**

That sentence is from a real prompt on this work and it is the single most
useful check in this file. It catches what a visual check misses.

Then state three things, explicitly:

- **Changed:** exactly what moved
- **Not changed:** the things named as off-limits, confirmed still intact
- **Noticed but left alone:** anything broken that you found and did not touch

## The pattern that keeps appearing

> "First, what is already confirmed working — do not redo or improve it."
> "Do not touch the enquiry form, the CRM submission, or anything outside these
> two pages."
> "Do not change slug, publisheddate, publishedat or status on any row."
> "Everything verified in prompts 1-5 must not regress."

Treat an unstated boundary the same way. If the user asked for two pages, the
third page is off-limits even though nobody said so.

## When the task is bigger than one change

Split it. One prompt, one concern. A prompt that fixes bugs **and** restructures
the sitemap will do neither cleanly, and when something breaks there is no way
to tell which half did it.

Say which part you are doing and that the rest follows separately.
