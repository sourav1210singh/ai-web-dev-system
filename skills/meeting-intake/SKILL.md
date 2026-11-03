---
name: meeting-intake
description: Take a meeting recording, transcript or client file and work out what it actually means - the whole of it, nothing skipped, screen as well as speech - then say what has to be done, how, and why. Use whenever a video, audio file, transcript, minutes, brief or client document is handed over, or a path to one is given. This is the one for a SINGLE recording, transcript or set of minutes. When it arrives with scope documents, a crawl or a folder of other material, project-intake runs the whole thing and calls this for the recording. Triggers on "meeting", "recording", "transcript", "minutes", "call", "meeting ka video", "video dekho", "call sun ke batao", "kya decide hua".
---

# Read the whole thing before deciding anything

A meeting is where the work gets decided. If a quarter of it is skimmed, the
quarter that was skipped is where the instruction was.

The job is not a summary. It is: **what was decided, what has to be done, how,
why, and what is still open.** A summary nobody can act on has wasted the
meeting.

## Start with the tool, not the transcript

```bash
python "C:\Claude-Code\.ai-system\skills\meeting-intake\meeting.py" <video> \
  --transcript <file> --out "<project>\meeting-<date>" --every 90
```

With no transcript, add `--transcribe` (whisper, roughly 0.6x real time with
`tiny`; use `--model base` when the audio is poor or names matter).

It measures the recording, checks the transcript against that length, pulls
frames across the whole of it, and writes a workspace. It judges nothing.

## Why the frames matter as much as the words

**What is on a shared screen is almost never read out loud.** A number, a URL,
a spreadsheet, a layout, a file name, a date on a calendar: all of it exists
in the recording and in none of the transcript. A transcript-only reading of a
screen-share meeting misses the content of the meeting.

So: open every frame the script produced. Not a sample of them. If one shows a
screen-share starting, pull denser frames around it:

```bash
ffmpeg -nostdin -v error -ss 540 -t 120 -i <video> -vf "fps=1/10,scale=1280:-2" -q:v 4 out/zoom_%02d.jpg
```

## A supplied transcript is a claim, not the recording

The script reports its coverage. Act on what it says:

- **A gap in the middle** usually means a speaker was not captured, not that
  nobody spoke. Read those minutes off the frames, or transcribe the audio.
- **Short at the end** is the dangerous one. Meetings decide things in the
  last five minutes.
- **No timestamps at all** means the transcript cannot be checked. Say so
  rather than treating it as complete.

Minutes written by a notetaker are a second-hand account. When a decision
matters, go to the transcript line, and when the transcript is thin, go to the
frame.

## Read the project before you interpret the meeting

Do this before forming a view, not after. The meeting is a continuation of
everything already agreed, and a sentence that looks like a new instruction is
often a repeat of a standing one.

- `<project>/CLAUDE.md` and `.claude-context/CONTEXT-*.md`
- `<project>/.claude-context/memory/` - the client's own rules, what they have
  already refused, what they asked for and were given
- any status file the project keeps, and the client log

A project where the client has said "never put a price on the site" changes
how you read a sentence about pricing. Without that, the meeting reads as a
new requirement and the standing rule gets broken.

## What the brief has to answer

Write it into the project, in English, as `meeting-<date>-brief.md`:

1. **What this meeting was about**, in two lines.
2. **What was decided.** Each one with the timestamp it was decided at, so
   anyone can go and hear it.
3. **What has to be done.** Each item: the action, who it is on, and what
   "done" looks like.
4. **How**, where the meeting said how. Where it did not, say what you propose
   and why.
5. **Why.** The reason behind each decision, because the reason is what lets
   you make the next call without asking.
6. **What is still open**, split into what the client has to answer and what
   can be decided here.
7. **What was said that contradicts something already agreed.** This is the
   most valuable section and the easiest to leave out.

## Four labels, never mixed

Every line in the brief is one of these, and says which:

- **Said** - it is in the transcript, with the timestamp.
- **Shown** - it was on screen, with the frame.
- **Inferred** - a reasonable reading, marked as yours.
- **Not covered** - the meeting did not settle it.

Never promote an inference to a decision. A brief that states something the
meeting did not decide will be acted on, and the client will be told their
instruction was followed when it was invented.

## Then verify before acting

The meeting says what people believe. Before building on it, check the
specific claims a developer can check: the live page, the repository, the
database, the admin. People misremember what is already live, and a request to
"add" something it already has is common.

Where the meeting and reality disagree, say so with both pieces of evidence.
That disagreement is usually the most useful thing to come out of the hour.

## Asking

Only what genuinely cannot be settled from the recording, the project and the
evidence. Decide the rest and show the reasoning. When you do ask, follow the
rules in `client-reply`: one question, answerable in a line, with your default
in it.
