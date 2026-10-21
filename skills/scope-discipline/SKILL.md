---
name: scope-discipline
description: Change only what was asked, prove nothing else moved, and never re-do work that is already confirmed working. Use before and after any edit to a live client site, any multi-page change, any migration, and any time a previous session already verified something. Triggers on "sirf ye change karo", "baaki mat chhedna", "don't touch", "regression", "kuch aur to nahi toota", or any edit to a site that is already live.
---

# Change only what was asked

Almost every prompt written on these projects carries a list of what must not be
touched. That is not caution, it is experience: the expensive failures here were
not bad edits, they were edits that quietly broke something adjacent.

## Before you touch anything

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
