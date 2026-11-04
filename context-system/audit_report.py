# -*- coding: utf-8 -*-
"""Turn audit.json into a plain report of what sits in the wrong folder."""
import io, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctxlib as c

ROOT = os.path.abspath(c.ROOT)
SKIP = {".context-system"}
SKIP_PARTS = {".claude-context", ".claude", "node_modules", ".git",
              "__pycache__", ".next", "dist", ".playwright-mcp"}


def top_folder(path):
    p = os.path.abspath(path)
    if not os.path.normcase(p).startswith(os.path.normcase(ROOT) + os.sep):
        return None
    rest = p[len(ROOT) + 1:]
    return rest.split(os.sep)[0] if rest else None


def main():
    data = json.load(io.open(os.path.join(HERE, "audit.json"), encoding="utf-8"))
    file_owner = data["file_owner"]
    proj_files = data["proj_files"]

    # ---------------------------------------------- 1. cross-folder writes
    cross = {}          # (home, project) -> {other_folder: [files]}
    outside = {}        # (home, project) -> [files outside the workspace]
    moved_ok = 0
    for f, owners in file_owner.items():
        tf = top_folder(f)
        for key in owners:
            home = key.split("||")[0]
            # A path recorded in an old transcript may have been tidied since.
            # If the file is gone from where it was written but is now sitting
            # in this project's own folder, that is the move, not a mistake.
            if tf != home and not os.path.isfile(f):
                here = os.path.join(ROOT, home, os.path.basename(f))
                if os.path.isfile(here):
                    moved_ok += 1
                    continue
                found = False
                for dp, dn, fn in os.walk(os.path.join(ROOT, home)):
                    dn[:] = [x for x in dn if x not in SKIP_PARTS]
                    if os.path.basename(f) in fn:
                        found = True
                        break
                if found:
                    moved_ok += 1
                    continue
            if tf is None:
                if ("\\AppData\\" in f or "\\Temp\\" in f
                        or "\\.claude\\" in f):
                    continue                     # scratch, already filtered
                outside.setdefault(key, []).append(f)
            elif tf != home:
                cross.setdefault(key, {}).setdefault(tf, []).append(f)

    # ------------------------------------- 2. disk files nobody here claims
    on_disk = {}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_PARTS and d not in SKIP]
        tf = top_folder(dirpath) or ""
        if not tf or tf in SKIP:
            continue
        for fn in filenames:
            if fn == "CLAUDE.md":
                continue
            on_disk.setdefault(tf, []).append(os.path.join(dirpath, fn))

    owner_tops = {}     # folder -> set of projects that wrote into it
    for f, owners in file_owner.items():
        tf = top_folder(f)
        if tf:
            owner_tops.setdefault(tf, set()).update(owners)

    folders = sorted(set(list(on_disk) + list(owner_tops)))

    L = []
    L.append("=" * 74)
    L.append("A. FILES WRITTEN INTO ANOTHER PROJECT'S FOLDER")
    L.append("=" * 74)
    if moved_ok:
        L.append("  (%d file(s) were written elsewhere but have since been moved"
                 % moved_ok)
        L.append("   into their own project folder - not counted as a problem)")
        L.append("")
    if not cross:
        L.append("  none")
    for key in sorted(cross):
        home, label = key.split("||")
        for other, fs in sorted(cross[key].items()):
            L.append("")
            L.append("  project : %s   (home folder: %s)" % (label, home))
            L.append("  wrote   : %d file(s) into  %s\\" % (len(fs), other))
            for f in sorted(fs)[:6]:
                L.append("            %s" % os.path.relpath(f, ROOT))
            if len(fs) > 6:
                L.append("            ... and %d more" % (len(fs) - 6))

    L.append("")
    L.append("=" * 74)
    L.append("B. PROJECT FILES SAVED OUTSIDE C:\\Claude-Code")
    L.append("=" * 74)
    if not outside:
        L.append("  none")
    for key in sorted(outside):
        home, label = key.split("||")
        fs = sorted(outside[key])
        shown = []
        for f in fs:
            if not os.path.isfile(f):
                continue                      # already deleted, nothing to do
            copied = os.path.isfile(os.path.join(ROOT, home, os.path.basename(f)))
            shown.append("%s%s" % (f, "   [copy already in %s\\ - the original "
                                       "can be deleted]" % home if copied else ""))
        if not shown:
            continue
        L.append("")
        L.append("  project : %s   (home folder: %s)" % (label, home))
        for line in shown[:8]:
            L.append("            %s" % line)
        if len(shown) > 8:
            L.append("            ... and %d more" % (len(shown) - 8))

    L.append("")
    L.append("=" * 74)
    L.append("C. FOLDER BY FOLDER")
    L.append("=" * 74)
    L.append("%-28s %7s  %s" % ("FOLDER", "FILES", "PROJECTS THAT WROTE HERE"))
    for f in folders:
        n = len(on_disk.get(f, []))
        projs = sorted(set(k.split("||")[1] for k in owner_tops.get(f, [])))
        note = ", ".join(projs) if projs else "-- nothing recorded --"
        L.append("%-28s %7d  %s" % (f[:28], n, note[:90]))

    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(L))


if __name__ == "__main__":
    main()
