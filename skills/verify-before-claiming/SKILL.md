---
name: verify-before-claiming
description: What counts as proof, by the kind of claim, and the answer shape for anything a client will read. Also the rule that nothing with a visual form - a PDF, Word or Excel file, video, recording, image, design or page - is ever described from its extracted text: it is rendered into images and looked at first. Nothing is reported as done, fixed, working, live or deployed until that same piece of work has been checked, from more than one angle, with the result looked at. Use before writing any reply that states an outcome, and whenever a tool or another agent reports success. Triggers on "done", "ho gaya", "kar diya", "fixed", "is it working", "verify karo", "test karo", "check karo", "confirm", "ye file dekho", "ye video dekho", "ye pdf dekho", "dekh ke batao", "kaisa lag raha hai", "screenshot".
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

### The same rule for a file, not only a page

A parser returns the words in a document and drops everything else without
saying so, and silence reads exactly like there was nothing there. So anything
with a visual form - a PDF, a Word, Excel or PowerPoint file, a video, an audio
recording, a photograph, a design - is **rendered into images and opened**
before a word is said about what is in it.

```bash
python "C:\Claude-Code\.ai-system\skills\verify-before-claiming\render.py" \
  <file-or-url...> --out "<project>\rendered" --pages 12 --every 90
```

A PDF becomes page images. A .docx, .xlsx or .pptx gives up the pictures buried
in its zip. A recording becomes frames across the whole of it. A page becomes
screenshots at phone and desktop width. An image too large to open comes back
scaled. Then **open every file it lists** - it prints the count on purpose, and
that is the number to open, not a suggestion.

What this has already caught:

- **A client's whole project schedule existed only as an embedded chart.** Text
  extraction returned 3,504 words from the document and not one of them was a
  date on it: the hand-over deadline, the staging sign-off, the go-live and the
  support window were all in a picture. A brief written from the text would
  have had no schedule in it and would not have said so.
- **A table in a PDF extracts as prose.** `pdftotext -layout` interleaves the
  columns, so a clean three-column table comes out as a run-on sentence. Diffed
  against the same document as a .docx that produced 960 "changes", none of
  them real. As a page image the table was readable and added up.
- **What is on a shared screen is never read out loud**, so it is in the
  recording and in none of the transcript.
- **A share card that measured perfectly was unusable** - correct dimensions,
  correct margins, white logo on bright concrete. Every measurement passed.

**Say what you could not see.** The tool reports what it failed to render
rather than skipping it, and so do you. LibreOffice is not installed here, so a
.docx page layout cannot be rendered at all: the words come from the text, the
pictures come out of the zip, and the layout is simply unseen. "I read the text
and recovered one embedded chart; the page layout I have not seen" is honest.
Describing the document as though you had read it is not. A file that produced
nothing to look at is a finding, not a blank.

## What counts as proof

| Claim | What proves it |
|---|---|
| the page works | HTTP status read from the live URL, plus a screenshot at 390 and 1440 |
| the form works | a real test submission, then the row, email or admin entry confirmed to have arrived |
| it is deployed | the build hash changed. Not the deploy tool saying success |
| a deploy landed | a string only the new code contains, found in the served bundle. Not the deployment id, which changes either way |
| it is fixed | the failure reproduced first, then shown gone |
| content matches | an element-by-element diff. Never a grep, never a word count |
| nothing else broke | the rendered HTML diffed against the capture taken before the change |
| the code is correct | the build or the tests actually run, with their output |
| a setting is saved | the admin page reloaded and the value read back, with cache bypassed |
| a file uploaded | a checksum compared. Upload tools report success on failure |
| what a document says | its pages rendered and looked at. Never its extracted text, which drops every table, chart and diagram in silence |
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
- **A scroll you did not confirm.** On a page running a smooth-scroll
  library, `window.scrollTo` and `scrollIntoView` return normally and move
  nothing. Anything that mounts on becoming visible then stays absent, and it
  reads as missing content. Drive a real wheel event and read `scrollY` back
  before believing you are where you think you are. This was reported as lost
  content four separate times before the cause was found.
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
