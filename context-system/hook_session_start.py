# -*- coding: utf-8 -*-
"""SessionStart hook: tell the new session what carry-over context exists here.

Emits hookSpecificOutput.additionalContext so a session on ANY Claude account
immediately knows which CONTEXT file to read. Never fails the session.
"""
import io, json, os, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
LOG = os.path.join(HERE, "hook.log")
MAX_CHARS = 4000


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as fh:
            fh.write(msg.rstrip() + "\n")
    except Exception:
        pass


def main():
    import ctxlib as c
    from hook_stop import resolve_folder

    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    cwd = payload.get("cwd") or os.getcwd()

    from hook_stop import load_routes
    route = load_routes().get(payload.get("session_id") or "")
    folder = (route or {}).get("folder") or resolve_folder(cwd, c.ROOT)
    if not folder:
        c.heartbeat("SessionStart", "skipped (not a project folder): %s" % cwd)
        return
    moved_note = ""
    if route and os.path.normcase(os.path.abspath(folder)) != \
            os.path.normcase(os.path.abspath(cwd)):
        moved_note = (
            "**This project has moved.** This chat was started in `%s`, but "
            "**%s** now lives in `%s` - its files and its history are both "
            "there. Old paths under the previous folder no longer exist, so "
            "work in the new one.\n\n" % (cwd, route.get("label", "it"), folder))
    index = os.path.join(c.ctx_dir_for(folder), "INDEX.md")
    if not os.path.isfile(index):
        c.heartbeat("SessionStart", "no context yet in %s" % folder)
        return
    body = c.read(index)
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n...(truncated, open INDEX.md for the rest)"

    streams = c.project_streams(folder)
    hint = ""
    if len(streams) == 1:
        hint = ("Read `%s` before you start.\n"
                % os.path.relpath(streams[0][2][-1], folder).replace("\\", "/"))
    elif len(streams) > 1:
        hint = ("This folder holds %d separate projects. Work out which one this "
                "request is about and read that project's newest CONTEXT file "
                "before you start.\n" % len(streams))

    ctx = ("## Carry-over project context (auto-loaded)\n\n%s"
           "Past work in this folder is recorded on disk so it survives switching "
           "Claude accounts. %s\n%s\n" % (moved_note, hint, body))

    out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                  "additionalContext": ctx},
           "suppressOutput": True}
    sys.stdout.write(json.dumps(out))
    c.heartbeat("SessionStart", "injected %d chars for %s"
                % (len(ctx), os.path.relpath(folder, c.ROOT)))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("SESSIONSTART ERROR\n" + traceback.format_exc())
    sys.exit(0)
