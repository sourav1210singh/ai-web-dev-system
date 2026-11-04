# -*- coding: utf-8 -*-
"""Shared helpers for the Claude-Code project context system.

Layout produced:
  <project folder>/CLAUDE.md                    -> auto-read by Claude Code
  <project folder>/.claude-context/config.json  -> {"mode":"single"|"multi", "map":{sid:slug}}
  <project folder>/.claude-context/INDEX.md     -> list of projects + files
  single mode: .claude-context/CONTEXT-01.md, CONTEXT-02.md, ...
  multi  mode: .claude-context/<project-slug>/CONTEXT-01.md, ...
"""
import io, json, os, re, unicodedata

WORD_LIMIT   = 10000          # hard cap per CONTEXT file, as requested
ENTRY_WORDS  = 400            # cap for one appended live entry
CTX_DIRNAME  = ".claude-context"
# The workspace is the folder this system was installed into: the one
# holding the projects, the context files and the memory. Worked out
# from this file's own location, so a clone onto another machine or
# into another folder needs no editing.
def _workspace():
    """The folder holding the projects, worked out from this file.

    Installed, this file sits in <workspace>/.context-system, so one step
    up is the answer. In the published repo it sits one level deeper, in
    <workspace>/.ai-system/context-system, and without this step a tool
    run from the repo would quietly scan the wrong folder and find
    nothing, which looks exactly like having no history.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    up = os.path.dirname(here)
    if os.path.basename(up) == ".ai-system":
        return os.path.dirname(up)
    return up


ROOT         = _workspace()


# ---------------------------------------------------------------- text utils
def slugify(s, fallback="untitled"):
    if not s:
        return fallback
    s = unicodedata.normalize("NFKD", str(s))
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    return (s[:60].strip("-") or fallback)


def count_words(text):
    return len(text.split())


def trim_words(text, limit):
    w = text.split()
    if len(w) <= limit:
        return text
    return " ".join(w[:limit]) + " \u2026"


def oneline(text, limit_chars=None):
    t = " ".join(str(text or "").split())
    if limit_chars and len(t) > limit_chars:
        t = t[:limit_chars].rstrip() + "\u2026"
    return t


# ---------------------------------------------------------------- fs helpers
def read(path, default=""):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except Exception:
        return default


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def append(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- config
def ctx_dir_for(folder):
    return os.path.join(folder, CTX_DIRNAME)


def heartbeat(event, detail=""):
    """One line per hook run, so 'is it actually working?' is always answerable."""
    import datetime
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs.log")
    try:
        line = "%s  %-12s %s\n" % (
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), event, detail)
        if os.path.isfile(p) and os.path.getsize(p) > 512 * 1024:
            keep = read(p).splitlines()[-2000:]
            write(p, "\n".join(keep) + "\n")
        append(p, line)
    except Exception:
        pass


def load_config(folder):
    p = os.path.join(ctx_dir_for(folder), "config.json")
    try:
        return json.loads(read(p, "{}")) or {}
    except Exception:
        return {}


def save_config(folder, cfg):
    write(os.path.join(ctx_dir_for(folder), "config.json"),
          json.dumps(cfg, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- stream dir
def stream_dir(folder, cfg, session_id, title):
    """Where this session's CONTEXT files live."""
    base = ctx_dir_for(folder)
    if (cfg.get("mode") or "single") == "single":
        return base
    mapping = cfg.get("map") or {}
    slug = mapping.get(session_id)
    if not slug:
        slug = slugify(title, "session-" + str(session_id)[:8])
    return os.path.join(base, slug)


# ---------------------------------------------------------------- rotation
_FILE_RE = re.compile(r"^CONTEXT-(\d{2,})\.md$")


def list_context_files(dirpath):
    out = []
    try:
        for fn in os.listdir(dirpath):
            m = _FILE_RE.match(fn)
            if m:
                out.append((int(m.group(1)), os.path.join(dirpath, fn)))
    except Exception:
        return []
    out.sort()
    return [p for _, p in out]


def file_header(n, folder, project, started):
    return (
        "# CONTEXT-%02d \u2014 %s\n\n"
        "- **Folder:** `%s`\n"
        "- **Project:** %s\n"
        "- **File started:** %s\n"
        "- **Word cap:** %d (a new CONTEXT-%02d.md opens when this one is full)\n\n"
        "> Carry-over memory for this project. Read this before working so the\n"
        "> history survives switching Claude accounts. Newest entries at the bottom.\n\n"
        "---\n\n"
    ) % (n, project, folder, project, started, WORD_LIMIT, n + 1)


def append_entry(dirpath, entry_md, folder="", project="", stamp=""):
    """Append one entry, rotating to a new file at WORD_LIMIT. Returns file path."""
    if not os.path.isdir(dirpath):
        os.makedirs(dirpath)
    files = list_context_files(dirpath)
    if not files:
        path = os.path.join(dirpath, "CONTEXT-01.md")
        write(path, file_header(1, folder, project, stamp))
        files = [path]
    cur = files[-1]
    cur_words = count_words(read(cur))
    add_words = count_words(entry_md)
    if cur_words and cur_words + add_words > WORD_LIMIT:
        n = int(_FILE_RE.match(os.path.basename(cur)).group(1)) + 1
        cur = os.path.join(dirpath, "CONTEXT-%02d.md" % n)
        write(cur, file_header(n, folder, project, stamp))
    append(cur, entry_md)
    return cur


# ---------------------------------------------------------------- index
def project_streams(folder):
    """[(project_label, dirpath, [files])] for a folder."""
    base = ctx_dir_for(folder)
    if not os.path.isdir(base):
        return []
    cfg = load_config(folder)
    if (cfg.get("mode") or "single") == "single":
        files = list_context_files(base)
        if not files:
            return []
        return [(cfg.get("project") or os.path.basename(folder), base, files)]
    out = []
    for name in sorted(os.listdir(base)):
        d = os.path.join(base, name)
        if os.path.isdir(d):
            files = list_context_files(d)
            if files:
                label = (cfg.get("labels") or {}).get(name, name)
                out.append((label, d, files))
    return out


def rebuild_index(folder):
    base = ctx_dir_for(folder)
    cfg = load_config(folder)
    mode = cfg.get("mode") or "single"
    streams = project_streams(folder)
    name = os.path.basename(folder.rstrip(chr(92)+chr(47)))
    lines = ["# Context index \u2014 %s" % name, ""]
    lines.append("- **Folder:** `%s`" % folder)
    lines.append("- **Mode:** %s (%s)" % (
        mode,
        "one project in this folder" if mode == "single"
        else "%d projects in this folder" % len(streams)))
    lines.append("- **Word cap per file:** %d" % WORD_LIMIT)
    lines.append("")
    if not streams:
        lines.append("_No context recorded yet._")
    for label, d, files in streams:
        lines.append("## %s" % label)
        rel = os.path.relpath(d, folder).replace("\\", "/")
        for f in files:
            w = count_words(read(f))
            fr = os.path.relpath(f, folder).replace("\\", "/")
            lines.append("- `%s` \u2014 %s words%s" %
                         (fr, "{:,}".format(w),
                          "  **\u2190 current**" if f is files[-1] else ""))
        lines.append("")
        _ = rel
    write(os.path.join(base, "INDEX.md"), "\n".join(lines).rstrip() + "\n")
    return os.path.join(base, "INDEX.md")
