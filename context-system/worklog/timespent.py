# -*- coding: utf-8 -*-
"""Time spent per project in a date range, from the transcripts.

    python timespent.py 2026-10-19 2026-10-24 [--detail]

Method, stated plainly because the number goes in front of people:

- Every message carries a timestamp. They are de-duplicated first, then
  sorted per project and split into bursts wherever the gap is longer than
  GAP minutes. A burst's length is its last timestamp minus its first.

- **De-duplication is not optional.** Forking a session copies its whole
  history into a new file, so the same minutes appear two or three times
  across files. Measured over one real week: 28,418 events, 9,001 distinct,
  a 3.16x inflation. Counting files naively triples the hours.

- A folder holding more than one project is split by what each burst is
  about, from the words in that burst's own prompts. A burst with no
  keyword of its own continues the previous one.

What it measures: time a Claude session was actively running on that work.
What it does NOT measure: work outside Claude - the Lovable editor, wp-admin,
email, calls, thinking. It is a floor for hands-on time, except where a long
build ran while the session idled, which inflates it instead.
"""
import io, json, os, re, sys
from collections import defaultdict
from datetime import datetime

ROOT = os.path.join(os.path.expanduser("~"), ".claude", "projects")
GAP = 30 * 60

# Which folder is which client, and which folders hold several projects, is
# this machine's own history: it names real clients and is worth nothing
# elsewhere. It lives in local_projects.py beside this file and is never
# published. Without it every folder is simply named after itself, which is
# correct for the folders holding one project and cannot split the folders
# holding several.
try:
    from local_projects import MULTI, LABEL
except ImportError:
    MULTI, LABEL = {}, {}


def nice(folder):
    if folder in LABEL:
        return LABEL[folder]
    # The same unsanitise range.py already does, rather than a second version
    # of it. Stripping the separators matters now that the labels are optional:
    # the old form left the root folder as "C  Claude Code" and a folder whose
    # name ends in a dash with a trailing space.
    n = folder.replace("C--Claude-Code", "").strip("-")
    return n.replace("-", " ") if n else "(root) Claude-Code"


def text_of(o):
    m = o.get("message") or {}
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c
                        if isinstance(b, dict) and b.get("type") == "text")
    return ""


def classify(folder, blob):
    rules = MULTI.get(folder)
    if not rules:
        return nice(folder)
    low = blob.lower()
    # Tier 1 is a named project, tier 2 a theme that runs through all of them.
    # A week spent moving every site onto git mentions "github" in every
    # prompt, which would otherwise swallow the client the work was for. If a
    # client is named at all, the work belongs to that client.
    for tier in (1, 2):
        best, score = None, 0
        for rule in rules:
            name, pat = rule[0], rule[1]
            if (rule[2] if len(rule) > 2 else 1) != tier:
                continue
            n = len(re.findall(pat, low))
            if n > score:
                best, score = name, n
        if best:
            return best
    return None


def gather(start, end):
    """Every event in range, de-duplicated, grouped by folder."""
    per_folder = defaultdict(dict)       # folder -> key -> (dt, human, text)
    raw = 0
    for d in sorted(os.listdir(ROOT)):
        pdir = os.path.join(ROOT, d)
        if not os.path.isdir(pdir):
            continue
        for f in sorted(os.listdir(pdir)):
            if not f.endswith(".jsonl"):
                continue
            try:
                fh = io.open(os.path.join(pdir, f), encoding="utf-8",
                             errors="replace")
            except Exception:
                continue
            with fh:
                for line in fh:
                    if '"timestamp"' not in line:
                        continue
                    try:
                        o = json.loads(line)
                    except Exception:
                        continue
                    ts = o.get("timestamp") or ""
                    if not (start <= ts[:10] <= end):
                        continue
                    try:
                        dt = datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")
                    except Exception:
                        continue
                    raw += 1
                    human = (o.get("type") == "user" and
                             (o.get("origin") or {}).get("kind") == "human")
                    txt = text_of(o) if human else ""
                    # a fork repeats the same event verbatim
                    key = (ts[:19], bool(human), txt[:80])
                    per_folder[d].setdefault(key, (dt, human, txt))
    return per_folder, raw


def measure(start, end):
    """The per-project totals, so another tool can read them.

    Pulled out of main() so `estimate.py` can compare a quote against these
    numbers without copying the de-duplication and burst logic. A second
    implementation of that would drift from this one and then two tools would
    disagree about the same week.
    """
    per_folder, raw = gather(start, end)
    kept = sum(len(v) for v in per_folder.values())

    projects = defaultdict(lambda: {"sec": 0, "prompts": 0, "days": set(),
                                    "bursts": 0})
    for folder, events in per_folder.items():
        rows = sorted(events.values(), key=lambda r: r[0])
        if not rows:
            continue
        bursts, cur = [], [rows[0]]
        for r in rows[1:]:
            if (r[0] - cur[-1][0]).total_seconds() > GAP:
                bursts.append(cur)
                cur = []
            cur.append(r)
        bursts.append(cur)

        last = None
        allblob = " ".join(r[2] for r in rows if r[1])
        for b in bursts:
            blob = " ".join(r[2] for r in b if r[1])
            if folder in MULTI:
                name = classify(folder, blob) or last or \
                    (nice(folder) + " (unclassified)")
                if not name.endswith("(unclassified)"):
                    last = name
            else:
                name = classify(folder, allblob)
            p = projects[name]
            p["sec"] += (b[-1][0] - b[0][0]).total_seconds()
            p["prompts"] += sum(1 for r in b if r[1])
            p["days"] |= set(r[0].strftime("%Y-%m-%d") for r in b)
            p["bursts"] += 1

    return dict(projects), raw, kept


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-10-19"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-10-24"
    detail = "--detail" in sys.argv
    projects, raw, kept = measure(start, end)

    rows = sorted(projects.items(), key=lambda kv: -kv[1]["sec"])
    total = sum(v["sec"] for _k, v in rows)
    print("# Time per project, %s to %s\n" % (start, end))
    print("events read %d, distinct %d (%.2fx duplication from forked "
          "sessions, removed)\n" % (raw, kept, raw / max(1, kept)))
    print("%-38s %9s %8s %6s" % ("Project", "Time", "Prompts", "Days"))
    print("-" * 66)
    for name, v in rows:
        if v["sec"] < 60 and not detail:
            continue
        h, m = int(v["sec"] // 3600), int((v["sec"] % 3600) // 60)
        print("%-38s %6dh %02dm %8d %6d"
              % (name[:38], h, m, v["prompts"], len(v["days"])))
    print("-" * 66)
    print("%-38s %6dh %02dm" % ("TOTAL", total // 3600, (total % 3600) // 60))
    print("\nGap over %d min counts as a break, not work." % (GAP // 60))


if __name__ == "__main__":
    main()
