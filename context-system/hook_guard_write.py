# -*- coding: utf-8 -*-
"""PostToolUse guard: a file meant to be kept must land in the project folder.

Warns (never blocks) when a Write/Edit lands in Downloads, Desktop, Documents,
the user's home root, or a DIFFERENT project's folder than the one in use.
Temp and scratchpad writes are fine and are ignored.
"""
import io, json, os, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOG = os.path.join(HERE, "hook.log")

HOME = os.path.join("C:\\", "Users", "admin")
STRAY = [os.path.join(HOME, x) for x in ("Downloads", "Desktop", "Documents",
                                         "OneDrive")]
IGNORE_PARTS = ("\\appdata\\", "\\temp\\", "\\scratchpad\\", "\\.git\\",
                "\\node_modules\\", "\\.claude\\")


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as fh:
            fh.write(msg.rstrip() + "\n")
    except Exception:
        pass


def under(path, parent):
    try:
        p = os.path.normcase(os.path.abspath(path))
        q = os.path.normcase(os.path.abspath(parent))
    except Exception:
        return False
    return p == q or p.startswith(q + os.sep)


def main():
    import ctxlib as c
    from hook_stop import resolve_folder, load_routes

    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    inp = payload.get("tool_input") or {}
    path = (payload.get("tool_response") or {}).get("filePath") \
        or inp.get("file_path")
    if not path:
        return
    low = os.path.normcase(os.path.abspath(path))
    if any(part in low for part in IGNORE_PARTS):
        return

    sid = payload.get("session_id") or ""
    cwd = payload.get("cwd") or os.getcwd()
    route = load_routes().get(sid)
    home_folder = (route or {}).get("folder") or resolve_folder(cwd, c.ROOT)

    msg = None
    for s in STRAY:
        if under(path, s):
            msg = ("Saved outside the project: `%s`.\nIf this is worth keeping, "
                   "copy it into %s and say where it came from."
                   % (path, home_folder or "the project folder"))
            break
    if msg is None and home_folder and under(path, c.ROOT) \
            and not under(path, home_folder):
        other = os.path.relpath(os.path.abspath(path),
                                os.path.abspath(c.ROOT)).split(os.sep)[0]
        if other.lower() != ".context-system":
            msg = ("Wrote into another project's folder: `%s` belongs to **%s**, "
                   "but this session is working in **%s**. Check that is "
                   "intended." % (path, other, os.path.basename(home_folder)))
    if not msg:
        return

    c.heartbeat("Guard", "stray write: %s" % path)
    sys.stdout.write(json.dumps({"systemMessage": msg}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("GUARD ERROR\n" + traceback.format_exc())
    sys.exit(0)
