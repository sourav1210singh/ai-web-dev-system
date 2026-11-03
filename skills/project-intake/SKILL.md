---
name: project-intake
description: Files were handed over with little or no instruction - a folder, a meeting recording, a transcript, a scope document, a crawl export, a client's old site - and the job is to work out by yourself what the project is, what has to be done, how and why, then stop and get that understanding approved before building anything. Use whenever a path, a folder or a set of files arrives and the request is thin, whenever a project folder appears with documents in it, and at the start of any new client. Triggers on "ye dekho", "ye files dekho", "ye folder dekho", "ye sab samjho", "meeting ka video h", "transcript bhi h", "scope of work", "client ne bheja h", "sir ne bheja h", "ab batao kya karna h", "kaam samjho", a bare file path, a bare folder path, or a message that is only attachments.
---

# Work it out, do not ask what it is

A folder was handed over. Nobody is going to explain it. The explanation is in
the files, and the job is to read all of them and come back with what the work
is - not with a question about what the work is.

**Do not ask "what should I do with these?"** That question hands the thinking
back. Read everything first. By the end of the reading there will be real
questions, and they will be worth asking.

## Stage 0 - read the project before reading the files

Always first, and in this order:

- `<project>/CLAUDE.md`
- `<project>/.claude-context/CONTEXT-*.md` and `.claude-context/memory/`
- `C:\Claude-Code\.claude-context\memory\MEMORY.md` - the standing rules
- the client log, if the project has one

A sentence in a scope document reads differently once you know what the client
has already refused. Interpreting first and reading the history afterwards is
how a standing instruction gets broken.

## Stage 1 - inventory and extract, before any opinion

```bash
python "C:\Claude-Code\.ai-system\skills\project-intake\materials.py" "<folder>" \
  --site https://<live-domain>/ --out "<project>\materials"
```

It reads every file it was given: PDF, .docx, .csv, .xlsx, .md, and it
measures every recording. It writes the full text of each document to
`materials\text\` and an inventory to `materials.json`. It judges nothing.

**Then read the text files, all of them, end to end.** The inventory is a map,
not the content. A 3,500 word scope document has about forty obligations in it
and the summary line has none of them.

## Stage 2 - the recording, if there is one

```bash
python "C:\Claude-Code\.ai-system\skills\meeting-intake\meeting.py" <video> \
  --transcript <file> --out "<project>\meeting-<date>" --every 90
```

Follow `meeting-intake` from there: every frame, not a sample, because what is
on a shared screen is never read out loud. If the intake says the transcript
stops early, the end of the meeting is missing, and that is where the
decisions are.

## Stage 3 - two versions of one document

This is the trap, and it arrives often: an old PDF and an updated doc, or a
scope and a revised scope. The script reports when it sees more than one.

```bash
python "C:\Claude-Code\.ai-system\skills\project-intake\materials.py" --diff \
  "<project>\materials\text\<old>.txt" "<project>\materials\text\<new>.txt"
```

**Never diff the two line by line.** The same document exported as a PDF and
as a .docx differs on almost every line, because `pdftotext -layout`
interleaves table columns while Word gives clean paragraphs. On a real pair
that produced 960 changed lines and not one of them was a revision. `--diff`
compares whole sentences and counts every figure on both sides, which is what
survives the formatting.

Reading its output:

- **The figure table is the money.** A count that appears in one and not the
  other is a revised estimate. Decimals that differ by a leading digit
  (`1.1` against `4.1`) are usually a table column bleeding into the next in
  the PDF, not a change - check the sentence they came from before raising it.
- **A dropped line and an added line that say the same thing** are one line
  reformatted. The finding is the entry with no partner: on the real pair,
  eighteen entries resolved to one new sentence, and that sentence extended
  the support period by a month. That is a scope change, and it was invisible
  in the line diff.
- **The newer one is not automatically the complete one.** A line that existed
  in the old version and is absent from the new one is either a deliberate cut
  or an accident, and only the client knows which.
- **List every difference** in the brief, under the heading
  "the two scope documents disagree about". Say which version you are working
  to and why.
- Never quietly work from one and ignore the other. The one you ignored is the
  one that gets quoted back at you.

## Stage 4 - the live site, and the counts

For a migration or a rebuild, the old site is a source document too. Run
`site-recon` for the domain, registrar, DNS, hosting, stack and email records,
and let it write into the project, never into the published system folder.

Then reconcile the three numbers that are never the same:

| source | what it says |
|---|---|
| the scope document | the page count it was priced against, and the date it was counted |
| the live sitemap | what the site claims today |
| the crawl export | what a crawler actually reached |

The script prints all three and flags a disagreement. **A disagreement is a
finding, not a nuisance.** Pages added since the scope was written are work
nobody has been paid for; pages in the crawl and not in the sitemap are
usually orphans; pages in the sitemap and not in the crawl are usually broken.
Each case changes the estimate, so each one goes in the brief.

## Stage 5 - the brief, and this is where it stops

Write `<project>/project-brief-<date>.md`, in English. It answers:

1. **What this project is**, in two lines.
2. **What has to be done.** Every obligation from every source, each one
   traced to where it came from: the document and page, the timestamp, the
   frame, or the crawl row.
3. **How**, where a source said how. Where none did, your proposal and the
   reason for it.
4. **Why.** The reason behind each decision, because the reason is what lets
   the next call be made without asking.
5. **Where the sources disagree.** Scope against scope, meeting against
   document, document against live site. The most valuable section and the
   easiest to leave out.
6. **What is still open**, split into what only the client can answer and what
   you have decided yourself.
7. **What it would take**, as a range, with what the range depends on.

Every line carries one of these labels, never mixed:

- **Said** - in the transcript, with the timestamp.
- **Shown** - on screen, with the frame.
- **Written** - in a document, with the file and page.
- **Inferred** - your reading, marked as yours.
- **Not covered** - no source settles it.

An inference is never promoted to a decision. A brief that states something
nobody decided will be built, and the client will be told their instruction
was followed when it was invented.

**Then stop.** Put the brief in front of the user and wait. Nothing is built,
no route is chosen, no prompt is sent, no file in the client's project is
changed until the brief comes back approved. This gate exists because a wrong
reading caught at the brief costs a paragraph and caught after the build costs
the build.

## Stage 6 onward - only after approval

In order, each one its own skill: `build-route` to decide where the work
happens, then the build, then `migration-parity` against every old page,
`responsive-qa`, `launch-files` and `seo-complete`, then
`verify-before-claiming`, then `client-reply`.

The standing rules do not loosen because a brief was approved:

- **Lovable**: write the prompt into the project and stop. Never press enter.
  Only when told to, in that same session. A Lovable project with a git repo
  is edited through git instead, which costs nothing.
- **WordPress**: the user signs in on their own profile. Never enter a
  credential.
- **Never test on a live client site.** The user nominates the target.
- **English** for every file, folder, commit and client-facing word.
- `leakcheck.py` before every push.

## Asking, when it is genuinely needed

Only what no source settles and no evidence can decide. Then, following
`client-reply`: one round, each question answerable in a line, your default
already in it, so a one-word reply is enough to proceed.

Good: "The October scope lists 40 tasks against 56 pages; the sitemap now has
61. I will treat the 5 new pages as in scope at the same rate unless you say
otherwise."

Bad: "Can you clarify the scope?"

Two rounds of questions on one point means the first round was written badly.
