---
name: migration-parity
description: Everything on the client's old page must exist on the page that replaces it - every heading, paragraph, phone number, email address, form field, image, alt text and outbound link. Use when rebuilding an existing site, moving a site to a new platform, replacing a page, or before any go-live that retires old URLs. Triggers on "migration", "old site", "purani website", "redesign", "rebuild", "content carry over", "same content", "old page se sab", "go live", "redirect".
---

# Nothing from the old page may quietly disappear

A redesign is judged on what the client notices is gone. They will not read
the new copy and admire it; they will look for their phone number, the
accreditation logo, the paragraph about the family business, the enquiry form
field that told them which branch the lead came from. Every one of those has
been lost in a rebuild before, and every one of them was lost silently.

A word count will not catch it. A grep will not catch it. A screenshot of the
new page will not catch it, because nothing looks wrong about a page that is
simply missing a section.

## Run it

```bash
python "C:\Claude-Code\.ai-system\skills\migration-parity\parity.py" <old> <new> --out <project>\.claude-context\qa
```

Both arguments are a URL **or** a saved HTML file. For a whole site, put the
pairs in a file, one `old-url<TAB>new-url` per line, and run `--map pairs.txt`.

It exits non-zero when something is missing, so it can gate a go-live claim.

## The client-rendered trap

If the new build is React, Next in client mode, Lovable, Vue or Svelte, the
server returns an empty shell and the content only exists after JavaScript
runs. Comparing against that shell would report that *everything* is missing,
or worse, be waved away as a false alarm.

The script detects the shell and refuses to compare, telling you to capture
the rendered HTML instead. Do that in the browser, save it, and pass the file:

```bash
python parity.py https://old-site.test/services rendered-services.html --out qa
```

**A page that could not be compared is never a pass.** The exit code says so.

## What it reports

**MISSING** is a blocker: a heading, a phone number, an email address, a form,
or main content coverage under 90%.

**CHECK** is for a person to judge: individual text blocks, outbound links,
internal links, alt text, a drop in image count, lost form fields, meta
description, structured data.

Two coverage figures are printed, and the second is the one that matters.
Whole-page coverage counts the nav and the footer, which match on every page
of the site and will hold the number up near 90% while half the real content
is gone. Main content coverage measures `<main>` alone (or the page with nav,
header, footer and aside removed). Judge on that one.

## What it cannot tell you

- Whether something was dropped **on purpose**. A service the client retired
  will show up as a missing heading. The script reports; you decide, and the
  decision goes in the client log so nobody re-litigates it in three months.
- Whether the new wording is any good. It matches reworded sentences on
  purpose, so a rewrite passes as long as the substance is there.
- Whether it *looks* right. That is a different check and it is not optional:
  run `responsive-qa` and read the screenshots. See `verify-before-claiming`.

## Order of work on a migration

1. Capture the old site first, while it is still up. Save the HTML of every
   page you are replacing. Once DNS moves, the original is gone and the
   archive may be incomplete.
2. Build the new page.
3. Run parity, pair by pair. Fix every MISSING.
4. Walk the CHECK list with the client's own words in front of you.
5. **Every old URL with no counterpart needs a 301.** A page that was removed
   deliberately still needs a destination, or its rankings and its backlinks
   go nowhere.
6. Then look at it: `responsive-qa` at 390 and 1440, and read the screenshots.
7. Re-run parity after go-live, against the live domain, because a build that
   passed in preview can ship differently.

## The thing to say to the client

Not "the content has been migrated". Say what was checked, what moved, what
was deliberately dropped and on whose instruction. The report file is the
evidence, and it is worth keeping next to the client log.
