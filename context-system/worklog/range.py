# -*- coding: utf-8 -*-
"""What was actually worked on between two dates, from the transcripts.

    python range.py 2026-10-12 2026-10-17 [--full]

Reads every Claude Code transcript, keeps the real human prompts, de-duplicates
the repeats that forked sessions produce, and groups what is left by project
folder and by day.
"""
import io, json, os, re, sys
from collections import defaultdict

ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
START = sys.argv[1] if len(sys.argv) > 1 else "2026-10-12"
END = sys.argv[2] if len(sys.argv) > 2 else "2026-10-17"
FULL = "--full" in sys.argv


def unsanitise(name):
    """C--Claude-Code-Some-Project -> Some Project (best effort)."""
    n = name.replace("C--Claude-Code", "").strip("-")
    return n.replace("-", " ") if n else "(root) Claude-Code"


def text_of(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        out = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                out.append(b.get("text", ""))
        return "\n".join(out)
    return ""


def main():
    seen = set()
    by_proj = defaultdict(lambda: defaultdict(list))
    files = 0
    for d in sorted(os.listdir(ROOT)):
        pdir = os.path.join(ROOT, d)
        if not os.path.isdir(pdir):
            continue
        for f in sorted(os.listdir(pdir)):
            if not f.endswith(".jsonl"):
                continue
            files += 1
            try:
                fh = io.open(os.path.join(pdir, f), encoding="utf-8",
                             errors="replace")
            except Exception:
                continue
            with fh:
                for line in fh:
                    if '"user"' not in line:
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    if o.get("type") != "user":
                        continue
                    if (o.get("origin") or {}).get("kind") != "human":
                        continue
                    ts = (o.get("timestamp") or "")[:10]
                    if not (START <= ts <= END):
                        continue
                    t = text_of(o.get("message") or {}).strip()
                    if not t or t.startswith("<"):
                        continue
                    key = (o.get("timestamp", "")[:19], t[:120])
                    if key in seen:
                        continue
                    seen.add(key)
                    by_proj[d][ts].append(t)

    print("transcript files scanned: %d" % files)
    print("unique human prompts in %s..%s: %d\n" % (START, END, len(seen)))

    for d in sorted(by_proj, key=lambda k: -sum(len(v) for v in by_proj[k].values())):
        total = sum(len(v) for v in by_proj[d].values())
        print("=" * 70)
        print("%s   [%d prompts]" % (unsanitise(d), total))
        for day in sorted(by_proj[d]):
            print("\n  %s  (%d)" % (day, len(by_proj[d][day])))
            for t in by_proj[d][day]:
                one = re.sub(r"\s+", " ", t).strip()
                print("    - %s" % (one if FULL else one[:160]))
        print("")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
