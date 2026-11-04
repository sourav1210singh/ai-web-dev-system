# -*- coding: utf-8 -*-
"""Build CONTEXT-NN.md files for every project from the Claude Code transcripts."""
import io, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ctxlib import (WORD_LIMIT, append_entry, ctx_dir_for, load_config, read,
                    rebuild_index, save_config, trim_words, write)
from ctxlib import ROOT as _ctx_root_value
from grouping import load_plan


def _ctx_root():
    return _ctx_root_value

PROMPT_WORDS = 30
OUT_WORDS = 40
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit", "MultiEdit")
URL_RE = re.compile(r'https?://[^\s)\]>"\'`]+')
CTX_FILE_RE = re.compile(r"^CONTEXT-\d+\.md$")

# --- secret hygiene: a CONTEXT file is meant to be read and shared, so values
# that look like credentials are masked before anything is written to disk.
SECRET_WORDS = ("secret", "token", "key", "pass", "pwd", "auth", "sig",
                "credential", "session", "access")
SECRET_KV_RE = re.compile(
    r"(?i)\b((?:api[_-]?)?(?:%s)[a-z_-]*)\s*[=:]\s*(['\"]?)([A-Za-z0-9_\-\.~+/]{16,})\2"
    % "|".join(SECRET_WORDS))
BEARER_RE = re.compile(r"(?i)\b(bearer|basic)\s+([A-Za-z0-9_\-\.~+/=]{16,})")
NOISE_PATH_RE = re.compile(r"(?i)\\(AppData|Temp|scratchpad|node_modules)\\|"
                           r"\.claude\\projects\\")


def redact(text):
    if not text:
        return text
    text = SECRET_KV_RE.sub(lambda m: "%s=***redacted***" % m.group(1), text)
    text = BEARER_RE.sub(lambda m: "%s ***redacted***" % m.group(1), text)
    return text


def interesting_file(path):
    """Keep real project files; drop temp, scratchpad and transcript-store paths."""
    return bool(path) and not NOISE_PATH_RE.search(path)

# The workspace is the folder this system was installed into: the one
# holding the projects, the context files and the memory. Worked out
# from this file's own location, so a clone onto another machine or
# into another folder needs no editing.
ROOT_DIR = _ctx_root()
MARK_BEGIN = "<!-- claude-context-system:begin -->"
MARK_END = "<!-- claude-context-system:end -->"


def blocks_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def extract_turns(path):
    """-> [ {ts, p, a, files[]} ] for one transcript file.

    A transcript can disappear between the inventory scan and the rebuild
    (Claude Code prunes old ones). One missing file must not abort the whole
    rebuild and wipe every other project's context.
    """
    if not os.path.isfile(path):
        sys.stderr.write("  transcript gone, skipping: %s\n" % os.path.basename(path))
        return []
    turns, cur = [], None
    for line in io.open(path, "r", encoding="utf-8", errors="replace"):
        if '"user"' not in line and '"assistant"' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = o.get("type")
        if t == "user" and o.get("origin", {}).get("kind") == "human":
            if cur:
                turns.append(cur)
            txt = " ".join(blocks_text(o.get("message", {}).get("content")).split())
            cur = {"ts": o.get("timestamp") or "", "p": txt, "a": "", "files": []}
        elif t == "assistant" and cur is not None:
            content = o.get("message", {}).get("content")
            if not isinstance(content, list):
                continue
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    s = " ".join(b.get("text", "").split())
                    if len(s) >= 15:
                        cur["a"] = s          # keep the latest substantial text
                elif b.get("type") == "tool_use" and b.get("name") in WRITE_TOOLS:
                    fp = (b.get("input") or {}).get("file_path")
                    if fp and fp not in cur["files"]:
                        cur["files"].append(fp)
    if cur:
        turns.append(cur)
    return turns


def collect_group(group):
    """Forked sessions repeat turns verbatim: dedupe on (timestamp, prompt).

    Returns (turns, last_ts_per_session).
    """
    seen, out, last = {}, [], {}
    for s in group["sessions"]:
        for t in extract_turns(s["path"]):
            sid = s["session_id"]
            if t["ts"] > last.get(sid, ""):
                last[sid] = t["ts"]
            key = (t["ts"], t["p"][:200])
            prev = seen.get(key)
            if prev is None:
                seen[key] = t
                out.append(t)
            else:
                if len(t["a"]) > len(prev["a"]):
                    prev["a"] = t["a"]
                for f in t["files"]:
                    if f not in prev["files"]:
                        prev["files"].append(f)
    out.sort(key=lambda x: x["ts"])
    return out, last


def overview(group, turns, folder):
    files, urls = {}, {}
    for t in turns:
        for f in t["files"]:
            if interesting_file(f):
                files[f] = files.get(f, 0) + 1
        for u in URL_RE.findall(t["p"])[:6]:
            u = redact(u.rstrip(".,"))
            urls[u] = urls.get(u, 0) + 1
    top_f = sorted(files.items(), key=lambda kv: -kv[1])[:15]
    top_u = sorted(urls.items(), key=lambda kv: -kv[1])[:12]
    L = ["## Project overview", "",
         "- **Project:** %s" % group["label"],
         "- **Folder:** `%s`" % folder,
         "- **Active:** %s to %s" % (group["first"][:10], group["last"][:10]),
         "- **Source:** %d transcript file(s), %d unique exchanges"
         % (len(group["sessions"]), len(turns)),
         ""]
    if top_u:
        L += ["### Links that came up", ""]
        L += ["- %s%s" % (u, ("  (x%d)" % n) if n > 1 else "") for u, n in top_u]
        L.append("")
    if top_f:
        L += ["### Files written or edited most", ""]
        L += ["- `%s`  (x%d)" % (f, n) for f, n in top_f]
        L.append("")
    L += ["### Transcripts behind this history", ""]
    for s in group["sessions"]:
        L.append("- `%s.jsonl` - %s to %s, %d prompts"
                 % (s["session_id"], (s["first_ts"] or "?")[:10],
                    (s["last_ts"] or "?")[:10], s["human_prompts"]))
    L += ["", "---", "", "## Work log", ""]
    return "\n".join(L) + "\n"


def entry_md(t):
    p = redact(trim_words(t["p"], PROMPT_WORDS)) or "(no text)"
    a = redact(trim_words(t["a"], OUT_WORDS))
    touched = [f for f in t["files"] if interesting_file(f)][:6]
    L = ["### %s <!-- ts:%s -->" % (t["ts"][:16].replace("T", " ") or "?", t["ts"]),
         "- **Asked:** %s" % p]
    if a:
        L.append("- **Result:** %s" % a)
    if touched:
        L.append("- **Touched:** %s" % ", ".join("`%s`" % f for f in touched))
    # How it was done, not only what came out. Months later this is the part
    # that answers "why did it do that", and a summary of the reply throws it
    # away.
    did = [redact(d) for d in (t.get("did") or [])][:8]
    if did:
        L.append("- **Did:** %s" % "; ".join(did))
    return "\n".join(L) + "\n\n"


def moved_note(folder):
    """If this folder's work used to live somewhere else, say so."""
    from grouping import RELOCATE, EXTRACT, folder_path_for
    target = os.path.basename(folder.rstrip("\\/"))
    olds, inside = [], []
    for (pdir, _slug), t in RELOCATE.items():
        if t == target:
            old = folder_path_for(pdir)
            if old and old not in olds:
                olds.append(old)
    for ex in EXTRACT:
        if ex["target"] == target:
            old = folder_path_for(ex["from_dir"])
            if old:
                inside.append((old, ex["ts_from"][:10]))
    if not olds and not inside:
        return []
    L = ["## Where this project came from", ""]
    for old in olds:
        L.append("- It used to be worked on from `%s`. Paths under that folder "
                 "no longer exist." % old)
    for old, day in inside:
        L.append("- Part of its history happened inside another project's chat "
                 "in `%s` (around %s) and was copied here, so the same turns "
                 "appear in both places." % (old, day))
    L += ["- Everything is here now: the files, the history and the memory.",
          "- Old notes may still quote the old paths; translate them to this "
          "folder instead of reporting a missing file.", ""]
    return L


def working_rules(folder):
    rel = ".claude-context"
    return [
        "## Where things go in this project", "",
        "Everything to do with this project stays inside `%s`." % folder,
        "Nothing that matters is written to Downloads, Desktop, Documents, the",
        "temp folder, or another project's folder.", "",
        "| What | Where |",
        "|---|---|",
        "| Deliverables, documents, exports, code | this folder (a sensible "
        "sub-folder is fine) |",
        "| Files downloaded or received for this client | `from-downloads/` |",
        "| Conversation history | `%s/CONTEXT-NN.md` (automatic) |" % rel,
        "| Facts worth remembering | `%s/memory/` (automatic) |" % rel,
        "| Throwaway scratch work | the session scratchpad, never this folder |",
        "",
        "Rules:", "",
        "1. Before saving anything a human will want later, put it under this",
        "   folder. If a tool can only write elsewhere, copy it back here and",
        "   say where it came from.",
        "2. Read the CONTEXT file above before starting, and prefer what it says",
        "   over guessing.",
        "3. Worth remembering (client decisions, credentials locations, URLs,",
        "   deadlines, things that went wrong) goes into memory, so the next",
        "   session on any Claude account still knows it.",
        "4. Do not write into another project's folder. If the work belongs to a",
        "   different client, say so and stop.",
        "",
    ]


def claude_md_block(mode, groups, folder=""):
    rel = ".claude-context"
    L = [MARK_BEGIN,
         "# Carry-over context for this folder",
         "",
         "Earlier work in this folder is recorded under `%s/`." % rel,
         "**Read the relevant CONTEXT file before starting work**, so the history",
         "survives switching to a different Claude account.",
         "",
         "- Index: `%s/INDEX.md`" % rel,
         "- Each CONTEXT file holds at most %s words; when one fills up the next"
         % "{:,}".format(WORD_LIMIT),
         "  numbered file (`CONTEXT-02.md`, `CONTEXT-03.md`, ...) is opened automatically.",
         "- Every new exchange is appended automatically after each reply.",
         ""]
    if mode == "single":
        L += ["This folder holds **one project**: **%s**." % groups[0]["label"],
              "History: `%s/CONTEXT-01.md` (plus any later numbers)." % rel, ""]
    else:
        L += ["This folder holds **%d separate project%s**. Open the one you are "
              "working on:" % (len(groups), "" if len(groups) == 1 else "s"), ""]
        for g in groups:
            L.append("- **%s** -> `%s/%s/`" % (g["label"], rel, g["slug"]))
        L.append("")
    if folder:
        L += moved_note(folder)
        L += working_rules(folder)
    L.append(MARK_END)
    return "\n".join(L) + "\n"


def install_claude_md(folder, mode, groups):
    p = os.path.join(folder, "CLAUDE.md")
    block = claude_md_block(mode, groups, folder)
    if os.path.isfile(p):
        cur = read(p)
        if MARK_BEGIN in cur and MARK_END in cur:
            new = re.sub(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END),
                         lambda m: block.strip(), cur, flags=re.S)
        else:
            new = cur.rstrip() + "\n\n" + block
        write(p, new)
    else:
        write(p, block)
    return p


def prune_stale(folder, mode, slugs):
    """Drop CONTEXT files left behind by a previous layout (e.g. after a mode
    switch). Only ever removes CONTEXT-NN.md files and the now-empty folders
    that held them -- anything else the user put there is left alone."""
    base = ctx_dir_for(folder)
    if not os.path.isdir(base):
        return
    keep = set(slugs)
    for name in os.listdir(base):
        path = os.path.join(base, name)
        if os.path.isfile(path) and CTX_FILE_RE.match(name) and mode != "single":
            os.remove(path)                       # stale single-mode leftovers
        elif os.path.isdir(path) and (mode == "single" or name not in keep):
            contents = os.listdir(path)
            if contents and all(CTX_FILE_RE.match(x) for x in contents):
                for x in contents:
                    os.remove(os.path.join(path, x))
                os.rmdir(path)


def run_extracts(plan, only):
    """Copy a time-window of another project's turns into its own folder."""
    from grouping import EXTRACT
    out = []
    for ex in EXTRACT:
        target = ex["target"]
        if only and only.lower() not in target.lower():
            continue
        folder = os.path.join(ROOT_DIR, target)
        if not os.path.isdir(folder):
            out.append("SKIP extract (no folder): %s" % folder)
            continue
        src = None
        for p in plan:
            if p["project_dir"] == ex["from_dir"]:
                for g in p["groups"]:
                    if g["slug"] == ex["from_slug"]:
                        src = g
        if src is None:
            out.append("SKIP extract (source project not found): %s" % ex["from_slug"])
            continue
        turns, _ = collect_group(src)
        sel = [t for t in turns if ex["ts_from"] <= t["ts"] <= ex["ts_to"]]
        if not sel:
            out.append("SKIP extract (no turns in window): %s" % target)
            continue
        d = ctx_dir_for(folder)
        for fn in list(os.listdir(d)) if os.path.isdir(d) else []:
            if CTX_FILE_RE.match(fn):
                os.remove(os.path.join(d, fn))
        g2 = {"label": ex["label"], "sessions": src["sessions"],
              "first": sel[0]["ts"], "last": sel[-1]["ts"]}
        head = overview(g2, sel, folder)
        head += ("> These turns happened inside the **%s** thread in `%s`, which is\n"
                 "> why they also appear there. Only the %s window belongs to this\n"
                 "> project.\n\n" % (src["label"], ex["from_dir"], ex["ts_from"][:10]))
        append_entry(d, head, folder, ex["label"], sel[0]["ts"][:10])
        for t in sel:
            append_entry(d, entry_md(t), folder, ex["label"], sel[0]["ts"][:10])
        save_config(folder, {"mode": "single", "project": ex["label"],
                             "extracted_from": ex["from_dir"],
                             "word_limit": WORD_LIMIT})
        write(os.path.join(d, ".state.json"), json.dumps({}, indent=1))
        rebuild_index(folder)
        install_claude_md(folder, "single", [{"label": ex["label"], "slug": ""}])
        out.append("%s  [EXTRACTED from %s]" % (folder, src["label"]))
        out.append("    %-34s %-36s turns=%-4d ctx_files=1"
                   % (ex["label"][:34], "-", len(sel)))
    return out


def write_session_routes(plan):
    """session id -> where its context belongs.

    A chat started before a project was moved still has the OLD folder as its
    cwd. Without this table the Stop hook would start a second, separate
    history there. The hook reads this first, so an old chat keeps writing
    into the project's real folder.
    """
    routes = {}
    for p in plan:
        folder = p["folder"]
        if not folder:
            continue
        mode = p["mode"]
        for g in p["groups"]:
            if not g.get("came_from"):
                continue            # only relocated projects need redirecting
            for s in g["sessions"]:
                routes[s["session_id"]] = {
                    "folder": folder,
                    "slug": "" if mode == "single" else g["slug"],
                    "label": g["label"],
                    "moved_from": g["came_from"],
                }
    write(os.path.join(HERE, "session_routes.json"),
          json.dumps(routes, indent=1, ensure_ascii=False))
    return len(routes)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    plan = load_plan()
    report = []
    for p in plan:
        folder, mode, groups = p["folder"], p["mode"], p["groups"]
        if only and only.lower() not in p["project_dir"].lower():
            continue
        if not folder or not os.path.isdir(folder):
            report.append("SKIP (folder not found on disk): %s" % p["project_dir"])
            continue
        # A mode the user set by hand (ctx.py mode ...) wins over the computed one.
        old = load_config(folder)
        locked = bool(old.get("mode_locked")) and old.get("mode") in ("single", "multi")
        if locked and old["mode"] != mode:
            mode = old["mode"]
            if mode == "single" and len(groups) > 1:
                main_g = groups[0]
                for g in groups[1:]:
                    main_g["sessions"].extend(g["sessions"])
                    main_g["prompts"] += g["prompts"]
                    main_g["first"] = min(main_g["first"], g["first"])
                    main_g["last"] = max(main_g["last"], g["last"])
                main_g["sessions"].sort(key=lambda s: (s["first_ts"] or ""))
                groups = [main_g]
        report.append("%s  [%s%s]" % (folder, mode.upper(),
                                      " locked" if locked else ""))
        cfg = {"mode": mode, "root_project_dir": p["project_dir"],
               "map": {}, "labels": {}, "word_limit": WORD_LIMIT}
        if locked:
            cfg["mode_locked"] = True
        state = {}
        for g in groups:
            turns, last_per_session = collect_group(g)
            base = ctx_dir_for(folder)
            d = base if mode == "single" else os.path.join(base, g["slug"])
            if os.path.isdir(d):
                for fn in os.listdir(d):                   # idempotent rebuild
                    if CTX_FILE_RE.match(fn):
                        os.remove(os.path.join(d, fn))
            stamp = g["first"][:10]
            append_entry(d, overview(g, turns, folder), folder, g["label"], stamp)
            for t in turns:
                append_entry(d, entry_md(t), folder, g["label"], stamp)
            for s in g["sessions"]:
                cfg["map"][s["session_id"]] = g["slug"]
            cfg["labels"][g["slug"]] = g["label"]
            if mode == "single":
                cfg["project"] = g["label"]
            # Seed the live-hook state with each session's OWN last turn, so the
            # Stop hook never re-appends something the backfill already wrote.
            state.update(last_per_session)
            n = len([x for x in os.listdir(d) if CTX_FILE_RE.match(x)])
            report.append("    %-34s %-36s turns=%-4d ctx_files=%d"
                          % (g["label"][:34], g["slug"][:36], len(turns), n))
        prune_stale(folder, mode, [g["slug"] for g in groups])
        save_config(folder, cfg)
        write(os.path.join(ctx_dir_for(folder), ".state.json"),
              json.dumps(state, indent=1))
        rebuild_index(folder)
        install_claude_md(folder, mode, groups)

    report += run_extracts(plan, only)
    n = write_session_routes(plan)
    if not only:
        import subprocess
        subprocess.call([sys.executable, "-X", "utf8",
                         os.path.join(HERE, "make_prompts.py")],
                        stdout=subprocess.DEVNULL)
        report.append("")
        report.append("START-PROMPT.md regenerated for every project")
    report.append("")
    report.append("session routes written: %d (old chats keep writing to the "
                  "right folder)" % n)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
