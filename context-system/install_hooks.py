# -*- coding: utf-8 -*-
"""Install (or remove) the context-system hooks in the user settings.json.

    python install_hooks.py            # install / repair
    python install_hooks.py --remove   # uninstall, leaving other hooks intact

Existing settings are read, merged and backed up; nothing else is touched.
"""
import io, json, os, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
TAG = "claude-context-system"
PY = sys.executable


AI_HOOKS = os.path.join(os.path.dirname(HERE), ".ai-system", "hooks")


def hook_entry(script, status=None, matcher=None):
    base = AI_HOOKS if script.startswith("hook_claim") else HERE
    h = {"type": "command", "command": PY,
         "args": ["-X", "utf8", os.path.join(base, script)],
         "timeout": 30, "_tag": TAG}
    if status:
        h["statusMessage"] = status
    g = {"hooks": [h]}
    if matcher:
        g["matcher"] = matcher
    return g


def is_ours(group):
    return any(isinstance(h, dict) and h.get("_tag") == TAG
               for h in (group.get("hooks") or []))


def load():
    if not os.path.isfile(SETTINGS):
        return {}
    return json.loads(io.open(SETTINGS, encoding="utf-8").read() or "{}")


def main():
    remove = "--remove" in sys.argv
    cfg = load()
    if os.path.isfile(SETTINGS):
        bak = SETTINGS + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
        shutil.copy2(SETTINGS, bak)
        print("backup: %s" % bak)

    hooks = cfg.setdefault("hooks", {})
    wanted = {
        "SessionStart": hook_entry("hook_session_start.py"),
        "Stop": [hook_entry("hook_stop.py", "Saving project context"),
                 hook_entry("hook_claim_gate.py", "Checking the claim")],
        "PostToolUse": hook_entry("hook_guard_write.py", None,
                                  "Write|Edit|MultiEdit|NotebookEdit"),
    }
    for event, entry in wanted.items():
        groups = [g for g in (hooks.get(event) or []) if not is_ours(g)]
        if not remove:
            # an event may carry more than one of our hooks
            groups.extend(entry if isinstance(entry, list) else [entry])
        if groups:
            hooks[event] = groups
        else:
            hooks.pop(event, None)
    if not hooks:
        cfg.pop("hooks", None)

    io.open(SETTINGS, "w", encoding="utf-8", newline="\n").write(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    print("%s: %s" % ("removed from" if remove else "installed into", SETTINGS))
    print(json.dumps(cfg.get("hooks", {}), indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
