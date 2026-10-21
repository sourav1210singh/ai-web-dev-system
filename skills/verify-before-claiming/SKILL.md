---
name: verify-before-claiming
description: What counts as proof, by the kind of claim, and the answer shape for anything a client will read. Nothing is reported as done, fixed, working, live or deployed until that same piece of work has been checked, from more than one angle, with the result looked at. Use before writing any reply that states an outcome, and whenever a tool or another agent reports success. Triggers on "done", "ho gaya", "kar diya", "fixed", "is it working", "verify karo", "test karo", "check karo", "confirm".
---

# Verify before claiming

The expensive failures here were never bad edits. They were one check,
believed.

A stale browser cache made a landed fix look like it had not landed, twice. A
stripped URL parameter made a live video look deleted. A regex that does not
match tabs left two bad rows in a 277-line redirect file that would have broken
a go-live. In every case a single angle was trusted.

## The gate

A `Stop` hook watches for a reply that claims work is complete. If files were
changed in that turn and nothing in the same turn went and looked, the turn is
blocked and sent back to verify. It blocks at most once per turn, so it cannot
loop, and a reply that is honest about not having checked is never blocked.

That hook is the floor, not the standard. It can only see that *something* was
checked. Whether the right thing was checked is yours.

```bash
python "C:\Claude-Code\.ai-system\install.py" --gate off   # and --gate on
```

## Looking at it is not optional

Reading the code does not tell you what the page looks like. Reading the DOM
does not either. A page can pass every technical check and still be visibly
broken: text overflowing its box, a button cut in half, two sections
overlapping, the wrong colour, an image that never loaded.

**Anything a person judges with their eyes gets a screenshot.** Every time, not
only when something seems wrong.

The gate enforces this as a second, stricter tier: when the turn changed a UI
file (`.tsx`, `.jsx`, `.css`, `.html`, `.php` and the rest) or the reply claims
something about a page, hero, header, button, layout, colour, font, animation
or anything else visual, **a screenshot is the only evidence that counts**. A
passing build, a green curl and a clean `git diff` do not clear it.

```bash
node "C:\Claude-Code\.ai-system\skills\responsive-qa\rqa.js" <url> --out <project>\.claude-context\qa
```

Six widths, screenshots and measurements. For a single check, the browser
pane's screenshot action is enough.

Then **read the screenshots**. Taking one and not looking at it is the same as
not taking it. If anything is wrong, fix it and look again before replying.

## What counts as proof

| Claim | What proves it |
|---|---|
| the page works | HTTP status read from the live URL, plus a screenshot at 390 and 1440 |
| the form works | a real test submission, then the row, email or admin entry confirmed to have arrived |
| it is deployed | the build hash changed. Not the deploy tool saying success |
| it is fixed | the failure reproduced first, then shown gone |
| content matches | an element-by-element diff. Never a grep, never a word count |
| nothing else broke | the rendered HTML diffed against the capture taken before the change |
| the code is correct | the build or the tests actually run, with their output |
| a setting is saved | the admin page reloaded and the value read back, with cache bypassed |
| a file uploaded | a checksum compared. Upload tools report success on failure |
| a count or a total | reconciled two independent ways, and the disagreement explained |

## Three or four angles, not the same one repeated

Running the same request three times is one check. Different angles means
different layers:

- the code, and the built bundle, which may not match
- the live DOM in a browser
- the data layer: the database, the admin, the API
- the rendered page, looked at with your eyes

## Distrust these specifically

- **A green result, especially a cached one.** Check the build hash before
  believing a deploy landed.
- **Any agent's or tool's self-report.** A build agent saying "done" is a claim
  to verify. An upload tool printing "uploaded" has done so on a DNS failure.
- **A 403, a timeout or an empty response.** That may be about you, not the
  site. One client site returns 403 to a browser user agent and 200 to curl's
  own and to Googlebot. Try another identity before saying anything is down.
- **Your own tool's first result.** Three tools built here cried wolf on their
  first run: lazy-load placeholders read as broken images, a screen-reader skip
  link read as a tiny tap target, a blocked request read as a missing file.
  A finding you doubt is a finding to verify, not to dismiss.

## The answer shape

For anything a client will read, or any claim that matters, split it:

**Verified** — with how it was checked, briefly. "Submitted two test enquiries,
both arrived."

**Assumed** — what you are taking on trust and why.

**Not checked** — plainly. "I have not been able to confirm the email
deliverability; that needs access to the mailbox."

An honest gap is useful. A plausible guess is how an account is lost: a mockup
once carried an invented company history and the client called the work
"designed by AI".

## When it genuinely cannot be checked

Say so, say what you would need, and recommend the path that does not depend on
it. Never fill the gap with something that sounds right. Never promise an
outcome; commit to the diagnosis and the method until the data is in hand.

That answer is allowed, and the gate will not block it.
