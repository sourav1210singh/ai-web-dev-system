# -*- coding: utf-8 -*-
"""Audit: is every file sitting in the folder of the project that created it?

Reads every transcript, records which project wrote which file, then compares
that against what is actually on disk under C:\\Claude-Code.
"""
import io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctxlib as c
from grouping import load_plan

WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")
ROOT = os.path.abspath(c.ROOT)
SKIP_DIRS = {".context-system", ".claude-context", ".claude", "node_modules",
             ".git", "__pycache__", ".next", "dist", "build", "vendor"}


def writes_in(path):
    """-> set of absolute file paths written/edited in this transcript."""
    out = set()
    for line in io.open(path, "r", encoding="utf-8", errors="replace"):
        if '"tool_use"' not in line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if o.get("type") != "assistant":
            continue
        content = o.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if (isinstance(b, dict) and b.get("type") == "tool_use"
                    and b.get("name") in WRITE_TOOLS):
                fp = (b.get("input") or {}).get("file_path")
                if fp:
                    out.add(os.path.normpath(fp))
    return out


def top_folder(path):
    """Which top-level folder under the root does this path live in?"""
    try:
        p = os.path.abspath(path)
    except Exception:
        return None
    if not os.path.normcase(p).startswith(os.path.normcase(ROOT) + os.sep):
        return None
    rest = p[len(ROOT) + 1:]
    return rest.split(os.sep)[0] if rest else None


def main():
    plan = load_plan()
    # project -> files it wrote ; file -> projects that wrote it
    proj_files, file_owner = {}, {}
    for p in plan:
        home = os.path.basename(p["folder"]) if p["folder"] else p["project_dir"]
        for g in p["groups"]:
            key = (home, g["label"])
            s = proj_files.setdefault(key, set())
            for sess in g["sessions"]:
                sys.stderr.write("scan %s\n" % os.path.basename(sess["path"]))
                sys.stderr.flush()
                s |= writes_in(sess["path"])
            for f in s:
                file_owner.setdefault(f, set()).add(key)
    out = {
        "proj_files": {"%s||%s" % k: sorted(v) for k, v in proj_files.items()},
        "file_owner": {k: ["%s||%s" % x for x in sorted(v)]
                       for k, v in file_owner.items()},
    }
    io.open(os.path.join(HERE, "audit.json"), "w", encoding="utf-8").write(
        json.dumps(out, indent=1, ensure_ascii=False))
    print("wrote audit.json: %d projects, %d distinct files"
          % (len(proj_files), len(file_owner)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
