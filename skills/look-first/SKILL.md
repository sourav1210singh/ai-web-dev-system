---
name: look-first
description: Never describe a file you have not looked at. Anything with a visual form - a PDF, a Word or Excel or PowerPoint file, a video, an audio recording, a photograph, a web page, a design, a screenshot - gets rendered into images and opened, every time, before a single word is said about what is in it. Parsing text out of a file is not reading it. Use before reporting on, summarising, briefing from, comparing or building from any such file, and before telling anyone that a page, image or layout is done. Triggers on "ye file dekho", "ye video dekho", "ye image dekho", "ye pdf dekho", "ye doc dekho", "screenshot", "dekh ke batao", "kaisa lag raha hai", "design check karo", "ye padh ke batao", "summarise this", "what does this say", or any file path handed over with a question about its contents.
---

# Reading the text is not looking at the file

A parser gives you the words. It does not give you the document. Everything
that is not a word - a table, a chart, a diagram, a screenshot pasted into a
page, a layout, a colour, a thing on a shared screen - is dropped silently,
and silence reads exactly like "there was nothing there."

**So: render it, open it, look at it. Every time. Before saying anything.**

```bash
python "C:\Claude-Code\.ai-system\skills\look-first\render.py" <file-or-url...> \
  --out "<project>\rendered" --pages 12 --every 90
```

PDF becomes page images. A .docx, .xlsx or .pptx gives up the pictures buried
in it. A recording becomes frames across the whole of it. A web page becomes
screenshots at phone and desktop width. A photograph too large to open comes
back scaled.

Then **open every file it lists, with the Read tool.** Not a sample. The tool
prints the count on purpose; open that many.

## Five things this has already caught

- **A client's whole project schedule existed only as an embedded PNG.** Text
  extraction returned 3,504 words from the document and not one of them was a
  date on that chart: every milestone, the hand-over deadline, the staging
  sign-off, the go-live and the support window were in a picture. The brief
  written from the text would have had no schedule in it and would not have
  said so.
- **A table in a PDF reads as prose when extracted.** `pdftotext -layout`
  interleaves the columns, so a clean three-column table comes out as a run-on
  sentence. Diffed line by line against the same document as a .docx, that
  produced 960 "changes", none of them real. As a page image the table was
  immediately readable and added up.
- **What is on a shared screen is never read out loud.** A number, a URL, a
  spreadsheet, a layout: all of it is in the recording and in none of the
  transcript.
- **A share card that measured perfectly was unusable.** Correct dimensions,
  correct safe margins, and a white logo on bright concrete that nobody could
  read. The measurements all passed. Looking at it took two seconds.
- **The DOM says an element exists; only a picture says it is visible.** A
  node present in the accessibility tree can be behind an overlay, clipped,
  zero-height, or the same colour as what is behind it.

## What to render, and when

| Before you | Render |
|---|---|
| summarise or brief from a document | every page of it, plus its embedded pictures |
| act on a meeting | frames across the whole recording, not a sample |
| say a page, section or layout is done | the page at phone and desktop width |
| send an image or share card to a client | the image itself, at full size |
| compare an old page with its replacement | both pages, side by side |
| report a design matches a reference | both, and say what you compared |

## Say what you could not see

The tool reports what it could not render rather than skipping it, and so do
you. LibreOffice is not installed on this machine, so a .docx's page layout
cannot be rendered - the words come from the text extraction and the pictures
come out of the zip, and the layout is simply unseen. Write that down. "I read
the text and recovered one embedded chart; the page layout itself I have not
seen" is honest. Describing the document as if you had read it is not.

A file that produced nothing to look at is a finding, not a blank. Scanned
PDFs, an audio file with no video track, a page that would not load: each one
means something was handed over that nobody has actually seen yet.

## This is a floor, not a ceiling

`verify-before-claiming` decides what counts as proof for a claim. This decides
something narrower and absolute: **you do not get to describe what you have not
looked at.** Rendering is cheap, and the Stop hook's claim gate already blocks a
reply that makes a visual claim with no visual evidence behind it. Looking
first means never meeting that gate by accident.
