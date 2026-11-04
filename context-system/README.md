# Project context system

Keeps a plain-text memory of every project under `C:\Claude-Code`, so the
history is **not lost when you switch to a different Claude account**.

Nothing here talks to Claude's servers. It only reads the transcripts Claude
Code already writes to `~/.claude/projects\` and turns them into
Markdown files that live next to each project.

---

## What you get in every project folder

```
C:\Claude-Code\<Folder>\
├── CLAUDE.md                     <- Claude reads this automatically at startup
└── .claude-context\
    ├── INDEX.md                  <- list of projects + files + word counts
    ├── config.json               <- single/multi mode, session -> project map
    ├── .state.json               <- last recorded turn per session (stops duplicates)
    └── CONTEXT-01.md ...         <- the history itself
```

**One project in the folder** (`mode: single`)

```
.claude-context\CONTEXT-01.md
.claude-context\CONTEXT-02.md
```

**Several projects in the folder** (`mode: multi`) - each gets its own stream

```
.claude-context\first-client\CONTEXT-01.md
.claude-context\first-client\CONTEXT-02.md
.claude-context\second-client\CONTEXT-01.md
```

Every CONTEXT file stops at **10,000 words**. When one fills up, the next
number opens by itself - `CONTEXT-02.md`, `CONTEXT-03.md`, and so on.

---

## How it stays up to date

Two hooks in `~/.claude/settings.json`:

| Hook | When it runs | What it does |
|---|---|---|
| `SessionStart` | a session opens | injects that folder's `INDEX.md` so Claude knows what exists |
| `Stop` | after every reply | appends that exchange to the right CONTEXT file |
| `PostToolUse` | after a file is written | warns if it landed in Downloads, Desktop, Documents or another project's folder |

Each appended entry looks like:

```markdown
### 2026-10-09 13:40 <!-- ts:2026-10-09T13:40:12.004Z -->
- **Asked:** <your prompt, first 30 words>
- **Result:** <what was done, first 40 words>
- **Touched:** `C:\Claude-Code\...\index.html`
```

The hidden `ts:` marker plus `.state.json` make sure the same turn is never
written twice, even after `/clear`, resume or compaction.

A folder you create later needs no setup: the first time you work in it, the
hook creates `.claude-context\` and `CLAUDE.md` for it automatically.

---

## Commands

Run from this folder (or use `ctx.cmd` from anywhere):

```
python ctx.py status                        what exists right now
python ctx.py check                         verify every file
python ctx.py rebuild                       rebuild everything from the transcripts
python ctx.py rebuild "Some Client"        rebuild one folder
python ctx.py mode "Some Client" single        force one-project mode (sticks across rebuilds)
python ctx.py mode "Some Client" multi         force many-projects mode
python ctx.py rename "All" oldname "New Name"
python ctx.py off                           stop recording
python ctx.py on                            start recording again
```

`rebuild` regenerates history from the transcripts and **overwrites**
`CONTEXT-*.md`. Anything you typed into those files by hand is lost, so put
your own notes in a different file inside `.claude-context\`.

---

## Files here

| File | Purpose |
|---|---|
| `ctxlib.py` | word counting, file rotation, index building |
| `inventory.py` | scans all transcripts -> `inventory.json` |
| `grouping.py` | decides single vs multi and which sessions form one project |
| `backfill.py` | builds CONTEXT files from history |
| `hook_stop.py` | the after-every-reply recorder |
| `hook_session_start.py` | the at-startup context injector |
| `install_hooks.py` | adds/removes the hooks in settings.json (keeps a backup) |
| `verify.py` | checks word caps, numbering, structure, leaked secrets |
| `selftest.py` | 24 end-to-end tests against a throwaway folder |
| `ctx.py` / `ctx.cmd` | the control panel above |
| `session_routes.json` | chats started before a project moved, and where they now belong |
| `move_memory_into_projects.py` | points each project's auto-memory at its own folder |
| `memcheck.py` | is auto-memory landing inside the projects? |
| `hook_guard_write.py` | the stray-write warning |
| `make_prompts.py` | writes START-PROMPT.md for each project |
| `fix_memory.py` | carries a moved project's memory to its new folder |
| `home_scan.py` | what project material sits in Downloads/Desktop/Documents |
| `collect_from_home.py` | copies that material into `<project>rom-downloads\` |
| `runs.log` | one line per hook run - check here to confirm it is recording |
| `hook.log` | only written when a hook hits an error |

---

## Safety notes

- A hook failure never breaks your session: errors go to `hook.log` and the
  hook always exits 0.
- Values that look like secrets (`secret=`, `token=`, `api_key=`, `Bearer ...`,
  16 characters or longer) are replaced with `***redacted***` before anything
  is written. Short secrets and ones with no recognisable label can still slip
  through, so skim a file before you share it outside your team.
- Temp paths, `node_modules` and the transcript store are filtered out of the
  "Touched" lists.
- `install_hooks.py` backs up `settings.json` before every change.
- `.context-system` itself is never recorded as a project.
- Hooks live in `~/.claude/settings.json`, which belongs to this **machine**, not
  to a Claude account - switching accounts keeps them. On a new PC, copy this
  folder and run `python install_hooks.py` once.

## How the grouping was decided

`grouping.py` groups a folder's sessions into projects using evidence from the
transcripts, not guesswork:

1. start from each session's title (the name shown in the Claude sidebar);
2. merge two groups when their first prompt is identical - that is a fork of
   the same thread, not a new project;
3. merge when one slug is a prefix of the other
   (`bkb-properties-cambodia` + `...-homepage-redesign`);
4. a short `OVERRIDES` table at the top of the file holds the two cases that
   were checked by hand, each with a comment saying why.

A folder ends up `single` when that leaves one group, `multi` when it leaves
more. `ctx.py mode` overrides the result permanently.

## Where a project's knowledge lives

Everything a project knows is inside its own folder:

```
C:\Claude-Code\<Project>\
├── CLAUDE.md
├── from-downloads\              <- client material collected out of Downloads
└── .claude-context\
    ├── CONTEXT-01.md ...        <- the conversation history
    └── memory\                  <- Claude Code's auto-memory for this project
```

Auto-memory normally lives at `~/.claude/projects/<sanitised-cwd>/memory/`,
outside the project and keyed to the working directory - so moving a folder
orphans it. Each project now carries
`.claude/settings.local.json` with `autoMemoryDirectory` pointing at its own
`.claude-context\memory\`, and the existing files were copied there. The old
copies are still in place, so nothing is lost either way.

Settings load at session start, so this takes effect from the next session.
`python ctx.py memcheck` compares both locations and says which one is
actually being written to.

## Moving a project to its own folder

Two tables at the top of `grouping.py` survive every rebuild:

- `RELOCATE` - a project whose work was run from another folder's cwd. Its
  history is filed under the folder its files actually live in.
- `EXTRACT` - work for a different client that happened inside another
  project's thread and cannot be split off as a session. The turns in the
  given time window are copied into the target folder; the source history is
  left whole.

After editing either, run `python ctx.py rebuild`. That also refreshes
`session_routes.json`, so a chat you started before the move keeps writing to
the project's real folder instead of starting a second history in the old one,
and its next session start is told the project has moved.
