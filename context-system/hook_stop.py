# -*- coding: utf-8 -*-
"""Stop hook: append the exchange that just finished to this project's CONTEXT file.

Reads the hook payload on stdin ({session_id, transcript_path, cwd, ...}).
Never fails the session: every error is swallowed and logged.
"""
import io, json, os, re, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LOG = os.path.join(HERE, "hook.log")
TAIL_BYTES = 8 * 1024 * 1024
TAIL_BYTES_MAX = 48 * 1024 * 1024


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as fh:
            fh.write(msg.rstrip() + "\n")
    except Exception:
        pass


def tail_lines(path, nbytes):
    size = os.path.getsize(path)
    start = max(0, size - nbytes)
    with io.open(path, "rb") as fh:
        fh.seek(start)
        data = fh.read()
    if start:
        nl = data.find(b"\n")
        data = data[nl + 1:] if nl >= 0 else b""
    return data.decode("utf-8", "replace").splitlines()


def blocks_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def last_exchange(path):
    """-> (ts, prompt, result, files, title) for the final human turn."""
    title = None
    for nbytes in (TAIL_BYTES, TAIL_BYTES_MAX):
        rows = []
        for line in tail_lines(path, nbytes):
            if ('"user"' not in line and '"assistant"' not in line
                    and "-title" not in line):
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
        for o in rows:
            if o.get("type") == "custom-title":
                title = o.get("customTitle") or o.get("title") or title
            elif o.get("type") == "ai-title" and not title:
                title = o.get("aiTitle") or title
        idx = None
        for i in range(len(rows) - 1, -1, -1):
            o = rows[i]
            if o.get("type") == "user" and o.get("origin", {}).get("kind") == "human":
                idx = i
                break
        if idx is None:
            continue
        u = rows[idx]
        ts = u.get("timestamp") or ""
        prompt = " ".join(blocks_text(u.get("message", {}).get("content")).split())
        result, files, did = "", [], []
        for o in rows[idx + 1:]:
            if o.get("type") != "assistant":
                continue
            content = o.get("message", {}).get("content")
            if not isinstance(content, list):
                continue
            for b in content:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text":
                    s = " ".join(b.get("text", "").split())
                    if len(s) >= 15:
                        result = s
                elif b.get("type") == "tool_use":
                    name = b.get("name") or ""
                    inp = b.get("input") or {}
                    if name in ("Write", "Edit", "NotebookEdit", "MultiEdit"):
                        fp = inp.get("file_path")
                        if fp and fp not in files:
                            files.append(fp)
                    act = action_of(name, inp)
                    if act and act not in did:
                        did.append(act)
        return ts, prompt, result, files, title, did
    return None, None, None, None, title, []


# Folders under the root that are plumbing, not client projects.
SKIP_FOLDERS = {".context-system"}


# What was actually done this turn, in a line a person can read months later.
# "Asked and Result" alone does not answer "how did it do it".
NOISE = re.compile(r"(?i)^(ls|cat|echo|cd|pwd|head|tail|wc|which|rm -rf __pycache__)\b")


def action_of(name, inp):
    low = (name or "").lower()
    if low in ("bash", "powershell"):
        cmd = " ".join(str(inp.get("command") or "").split())
        if not cmd or NOISE.search(cmd):
            return None
        return "ran `%s`" % (cmd[:150] + ("..." if len(cmd) > 150 else ""))
    if name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        return None            # already reported under Touched
    if name == "Read":
        fp = str(inp.get("file_path") or "")
        return ("looked at %s" % os.path.basename(fp)) if fp else None
    if "screenshot" in low or str(inp.get("action") or "") == "screenshot":
        return "took a screenshot"
    if "navigate" in low:
        return "opened %s" % str(inp.get("url") or "")[:90]
    if low.startswith("mcp__"):
        return "used %s" % name.split("__")[-1]
    if name in ("WebFetch", "WebSearch"):
        return "%s %s" % (name, str(inp.get("url") or inp.get("query") or "")[:80])
    return None


def load_routes():
    p = os.path.join(HERE, "session_routes.json")
    try:
        with io.open(p, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except Exception:
        return {}


def resolve_folder(cwd, root):
    """Map any cwd to the top-level project folder under C:\\Claude-Code."""
    try:
        cwd = os.path.abspath(cwd)
        root = os.path.abspath(root)
    except Exception:
        return None
    if os.path.normcase(cwd) == os.path.normcase(root):
        return root          # working at the root: keep a root-level stream
    cur = cwd
    while True:
        parent = os.path.dirname(cur)
        if os.path.normcase(parent) == os.path.normcase(root):
            # A dot-folder directly under the root (.context-system,
            # .ai-system, .claude) is plumbing, not a client project. Work
            # done while the shell happens to sit in one still belongs to the
            # root, so file it there rather than dropping it - otherwise turns
            # go missing whenever the cwd wanders.
            if os.path.basename(cur).startswith("."):
                return root
            return cur
        if not parent or parent == cur:
            return None
        cur = parent


def main():
    import ctxlib as c
    from backfill import entry_md, redact, interesting_file

    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd") or os.getcwd()
    sid = payload.get("session_id") or ""
    tpath = payload.get("transcript_path") or ""

    # A chat started before its project was moved still reports the old cwd.
    # The route table sends it to the folder the project actually lives in.
    route = load_routes().get(sid)
    folder = (route or {}).get("folder") or resolve_folder(cwd, c.ROOT)
    if not folder or not os.path.isdir(folder):
        c.heartbeat("Stop", "skipped (not a project folder): %s" % cwd)
        return
    if not tpath or not os.path.isfile(tpath):
        log("no transcript: %s" % tpath)
        return

    ts, prompt, result, files, title, did = last_exchange(tpath)
    if not ts or not prompt:
        return

    base = c.ctx_dir_for(folder)
    state_path = os.path.join(base, ".state.json")
    try:
        state = json.loads(c.read(state_path, "{}")) or {}
    except Exception:
        state = {}
    if state.get(sid) == ts:
        c.heartbeat("Stop", "already recorded, nothing to add")
        return

    cfg = c.load_config(folder)
    if route and cfg:
        # the route already says which stream this session belongs to
        slug = route.get("slug") or ""
        sdir = os.path.join(base, slug) if slug else base
        label = route.get("label") or os.path.basename(folder)
        turn = {"ts": ts, "p": prompt, "a": result or "", "files": files or [], "did": did or []}
        existing = c.list_context_files(sdir)
        if not (existing and ("<!-- ts:%s -->" % ts) in c.read(existing[-1])[-20000:]):
            c.append_entry(sdir, entry_md(turn), folder, label, ts[:10])
        state[sid] = ts
        c.write(state_path, json.dumps(state, indent=1))
        c.rebuild_index(folder)
        c.heartbeat("Stop", "saved -> %s (routed from %s)"
                    % (os.path.relpath(sdir, c.ROOT), route.get("moved_from", "?")))
        return
    if not cfg:
        # A folder the user added after setup: start it off on its own.
        # The root is treated as multi, since anything can be run from there.
        at_root = os.path.normcase(folder) == os.path.normcase(os.path.abspath(c.ROOT))
        cfg = {"mode": "multi" if at_root else "single",
               "map": {}, "labels": {}, "word_limit": c.WORD_LIMIT}
        if not at_root:
            cfg["project"] = title or os.path.basename(folder)
        c.save_config(folder, cfg)
    mode = cfg.get("mode") or "single"
    if mode == "single":
        sdir = base
        label = cfg.get("project") or os.path.basename(folder)
    else:
        slug = (cfg.get("map") or {}).get(sid)
        if not slug:
            slug = c.slugify(title, "session-" + sid[:8])
            cfg.setdefault("map", {})[sid] = slug
            cfg.setdefault("labels", {}).setdefault(slug, title or slug)
            c.save_config(folder, cfg)
        label = (cfg.get("labels") or {}).get(slug, slug)
        sdir = os.path.join(base, slug)

    # Second guard: the exact timestamp marker must not already be on disk.
    existing = c.list_context_files(sdir)
    if existing and ("<!-- ts:%s -->" % ts) in c.read(existing[-1])[-20000:]:
        state[sid] = ts
        c.write(state_path, json.dumps(state, indent=1))
        return

    turn = {"ts": ts, "p": prompt, "a": result or "", "files": files or [], "did": did or []}
    c.append_entry(sdir, entry_md(turn), folder, label, ts[:10])
    state[sid] = ts
    c.write(state_path, json.dumps(state, indent=1))
    c.rebuild_index(folder)
    ensure_claude_md(folder, cfg)
    c.heartbeat("Stop", "saved -> %s" % os.path.relpath(sdir, c.ROOT))


def ensure_claude_md(folder, cfg):
    """Keep the CLAUDE.md pointer in sync so a fresh account finds the context."""
    import ctxlib as c
    from backfill import (MARK_BEGIN, claude_md_block, install_claude_md,
                          install_rules_md)
    mode = cfg.get("mode") or "single"
    groups = [{"label": lbl, "slug": slug}
              for slug, lbl in sorted((cfg.get("labels") or {}).items())]
    if mode == "single":
        groups = [{"label": cfg.get("project") or os.path.basename(folder),
                   "slug": ""}]
    if not groups:
        return
    p = os.path.join(folder, "CLAUDE.md")
    block = claude_md_block(mode, groups, folder)
    cur = c.read(p) if os.path.isfile(p) else ""
    if not (MARK_BEGIN in cur and block.strip() in cur):
        install_claude_md(folder, mode, groups)
    # The rules block is a separate concern and must not sit behind the
    # pointer's "already current" check: the 24 folders that already had a
    # context block were current forever and so would never have been given
    # the rules at all. install_rules_md writes nothing when it is unchanged.
    install_rules_md(folder)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("ERROR\n" + traceback.format_exc())
    sys.exit(0)
