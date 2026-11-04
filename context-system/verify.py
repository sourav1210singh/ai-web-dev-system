# -*- coding: utf-8 -*-
"""Verify every generated CONTEXT file: word cap, structure, secret hygiene."""
import io, json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ctxlib as c

# things that would be a real leak if they survived redaction
LEAK_RE = re.compile(
    r"(?i)(?:secret|token|api[_-]?key|apikey|password|passwd|auth)"
    r"\s*[=:]\s*['\"]?([A-Za-z0-9_\-\.~+/]{16,})")
BAD = []
STATS = {"folders": 0, "projects": 0, "files": 0, "words": 0, "entries": 0}


def main():
    root = c.ROOT
    rows = []
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if not os.path.isdir(folder) or name.startswith("."):
            continue
        base = c.ctx_dir_for(folder)
        if not os.path.isdir(base):
            continue
        STATS["folders"] += 1
        cfg = c.load_config(folder)
        mode = cfg.get("mode") or "single"

        if not os.path.isfile(os.path.join(folder, "CLAUDE.md")):
            BAD.append("%s: CLAUDE.md missing" % folder)
        if not os.path.isfile(os.path.join(base, "INDEX.md")):
            BAD.append("%s: INDEX.md missing" % folder)
        if not os.path.isfile(os.path.join(base, ".state.json")):
            BAD.append("%s: .state.json missing" % folder)

        streams = c.project_streams(folder)
        if not streams:
            BAD.append("%s: no CONTEXT files" % folder)
        for label, d, files in streams:
            STATS["projects"] += 1
            for i, f in enumerate(files, 1):
                text = c.read(f)
                w = c.count_words(text)
                e = text.count("\n### ")
                STATS["files"] += 1
                STATS["words"] += w
                STATS["entries"] += e
                if w > c.WORD_LIMIT:
                    BAD.append("%s: %d words > %d" % (f, w, c.WORD_LIMIT))
                if not text.startswith("# CONTEXT-"):
                    BAD.append("%s: missing header" % f)
                if int(re.match(r"CONTEXT-(\d+)", os.path.basename(f)).group(1)) != i:
                    BAD.append("%s: numbering gap" % f)
                for m in LEAK_RE.finditer(text):
                    if "redacted" not in m.group(0).lower():
                        BAD.append("%s: possible secret -> %s" % (f, m.group(0)[:60]))
            rows.append((name, mode, label, len(files),
                         sum(c.count_words(c.read(x)) for x in files),
                         sum(c.read(x).count("\n### ") for x in files)))

    print("%-26s %-6s %-34s %5s %9s %8s" %
          ("FOLDER", "MODE", "PROJECT", "FILES", "WORDS", "ENTRIES"))
    for r in rows:
        print("%-26s %-6s %-34s %5d %9s %8d" %
              (r[0][:26], r[1], r[2][:34], r[3], "{:,}".format(r[4]), r[5]))
    print()
    print("folders=%d  projects=%d  context_files=%d  words=%s  entries=%s"
          % (STATS["folders"], STATS["projects"], STATS["files"],
             "{:,}".format(STATS["words"]), "{:,}".format(STATS["entries"])))
    print()
    if BAD:
        print("PROBLEMS (%d):" % len(BAD))
        for b in BAD[:40]:
            print("  - " + b)
        return 1
    print("VERIFY: all checks passed")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
