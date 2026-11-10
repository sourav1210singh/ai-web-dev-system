# -*- coding: utf-8 -*-
"""What we said it would take, against what it took.

    python estimate.py read    <file>
    python estimate.py record  <project> --from <file> --table N [--dated DATE]
    python estimate.py record  <project> --hours 40 --for "migration" --dated DATE
    python estimate.py approve <project> --all | --item "<text>" | --drop "<text>"
    python estimate.py compare <project> [--from DATE] [--to DATE]
    python estimate.py calibrate
    python estimate.py list

The actual hours come from `timespent.py`, imported rather than reimplemented,
so there is one definition of a working hour in this workspace and not two that
drift.

Three things this refuses to do, each because the real data made the reason
obvious:

- **It will not pick which number in a scope document is the estimate.** The
  first real estimate it was pointed at has a summary table billing 35 hours
  for a workstream whose own line items add up to 25. Any tool that silently
  sums tables returns 80, and any tool that silently picks one is right half
  the time. It prints what it found, says the totals disagree, and waits.

- **It will not compare against work the client never approved.** That same
  document quotes three workstreams and ends by asking which to proceed with.
  Compared against all three the project came in under; against the one that
  was priority work it came in over. Without recording what was approved the
  comparison has no meaning, so items start undecided and `compare` refuses
  while any still are.

- **It will not produce a calibration multiplier from a handful of projects.**
  A median of three is not a calibration, it is an anecdote with a decimal
  point. Under MIN_PROJECTS it prints the rows and says plainly that it is not
  enough.
"""
import io
import json
import os
import re
import sys
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import timespent  # noqa: E402

# The workspace root: .context-system/worklog -> .context-system -> root
ROOT = os.path.dirname(os.path.dirname(HERE))
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Below this, a median ratio is an anecdote. Stated rather than hidden so the
# number can be argued with.
MIN_PROJECTS = 5

HOURS_COL = re.compile(r"(?i)^\s*(hours?|hrs?|time|effort|days?)\s*$")
# A summary table names its rows after groups of work, not after tasks.
AGGREGATE = re.compile(r"(?i)workstream|phase|summary|section|scope|stream"
                       r"|category|group|milestone|deliverable")
NUM = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
MONEY = re.compile(r"([$£€₹]\s?[0-9][0-9,]*(?:\.[0-9]{2})?)")


# ----------------------------------------------------------------- reading

def docx_tables(path):
    """Every table in a .docx as rows of cell strings.

    A .docx is a zip and the body is word/document.xml, so no library is
    needed - the same approach project-intake's materials.py takes, and
    python-docx is not installed on this machine.
    """
    try:
        xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8")
    except Exception as e:
        raise SystemExit("could not read %s as a .docx: %s" % (path, e))
    root = ET.fromstring(xml)
    out = []
    for tbl in root.iter(W + "tbl"):
        rows = []
        for tr in tbl.iter(W + "tr"):
            cells = []
            for tc in tr.iter(W + "tc"):
                txt = "".join(n.text or "" for n in tc.iter(W + "t"))
                cells.append(" ".join(txt.split()))
            if any(c for c in cells):
                rows.append(cells)
        if len(rows) > 1:
            out.append(rows)
    return out


def hours_tables(tables):
    """Only the tables that have a column of hours, with that column found."""
    found = []
    for rows in tables:
        head = [h.strip() for h in rows[0]]
        col = next((i for i, h in enumerate(head) if HOURS_COL.match(h)), None)
        if col is None:
            continue
        items, total = [], 0.0
        for r in rows[1:]:
            if col >= len(r):
                continue
            m = NUM.search(r[col])
            if not m:
                continue
            hrs = float(m.group(1))
            money = MONEY.search(" ".join(r))
            items.append({"task": r[0], "hours": hrs,
                          "cost": money.group(1).replace(" ", "") if money else None,
                          "note": r[2] if len(r) > 2 else "",
                          "approved": None})
            total += hrs
        if items:
            found.append({"head": head, "items": items, "total": round(total, 2)})
    return found


def reconcile(tables):
    """Which detail table accounts for which line of the summary.

    Subtracting one total from the others gets this wrong, and did: on the
    first real document it reported an 18 hour gap, which is the true 10 hour
    discrepancy plus an 8 hour workstream that simply has no detail table. The
    pairing is recoverable, so recover it rather than reporting a number that
    is the sum of two unrelated things: a detail table's total usually appears
    verbatim as a line in the summary.
    """
    if len(tables) < 2:
        return []
    # The summary is the table whose lines other tables' totals match. That
    # alone ties: a detail table can hold a line that happens to equal another
    # detail table's total, and then the tiebreak decided it - wrongly, on a
    # fixture where "Analytics setup 6" collided with a 6 hour detail total.
    # So rank by the match count, then by the header naming an aggregate, then
    # by the largest total, because a summary adds up its details.
    scores = []
    for i, t in enumerate(tables):
        mine = [it["hours"] for it in t["items"]]
        hits = sum(1 for j, o in enumerate(tables)
                   if j != i and any(abs(o["total"] - h) < 0.01 for h in mine))
        aggregate = 1 if any(AGGREGATE.search(h) for h in t["head"]) else 0
        scores.append((hits, aggregate, t["total"], -i))
    scores.sort(reverse=True)
    hits, _agg, _tot, negi = scores[0]
    s = -negi
    if not hits:
        return ["None of these tables accounts for another, so they may be "
                "separate quotes rather than a summary and its detail. Decide "
                "which one is the estimate of record."]
    out, claimed = [], set()
    for j, o in enumerate(tables):
        if j == s:
            continue
        match = next((it for it in tables[s]["items"]
                      if abs(it["hours"] - o["total"]) < 0.01), None)
        if match:
            claimed.add(match["task"])
            out.append("table %d (%g h) accounts for %r in table %d"
                       % (j, o["total"], match["task"][:46], s))
        else:
            near = min(tables[s]["items"],
                       key=lambda it: abs(it["hours"] - o["total"]))
            # Claimed as well: this table IS that line's detail, the arithmetic
            # just disagrees. Saying it "has no detail table" underneath would
            # contradict the line above it.
            claimed.add(near["task"])
            out.append("table %d (%g h) matches no line in table %d; nearest is "
                       "%r at %g h, a gap of %g hour(s)"
                       % (j, o["total"], s, near["task"][:40], near["hours"],
                          abs(near["hours"] - o["total"])))
    for it in tables[s]["items"]:
        if it["task"] not in claimed and not any(
                abs(o["total"] - it["hours"]) < 0.01
                for j, o in enumerate(tables) if j != s):
            out.append("%r (%g h) in table %d has no detail table"
                       % (it["task"][:46], it["hours"], s))
    if any("gap of" in l for l in out):
        out.append("A gap is either an unlabelled buffer or an arithmetic "
                   "mistake. Worth settling before the next quote reuses it.")
    return out


def cmd_read(args, flags):
    path = args[0] if args else ""
    if not os.path.isfile(path):
        return fail("no such file: %s" % path)
    if not path.lower().endswith(".docx"):
        print("Only .docx tables can be read reliably.\n")
        print("A PDF's table columns get interleaved by text extraction, and a "
              "wrong number here is worse than no number. Render the file and "
              "read it - see the verify-before-claiming skill - then record the "
              "figure you read with:\n")
        print('  python estimate.py record "<project>" --hours H --for "<label>" '
              '--dated YYYY-MM-DD --source "%s"' % os.path.basename(path))
        return 0

    tables = hours_tables(docx_tables(path))
    if not tables:
        return fail("no table with an hours column in %s" % os.path.basename(path))

    print("# %s\n" % os.path.basename(path))
    for i, t in enumerate(tables):
        print("## table %d  -  %s" % (i, " | ".join(t["head"])))
        for it in t["items"]:
            print("    %-56s %6g%s" % (it["task"][:56], it["hours"],
                                       "  " + it["cost"] if it["cost"] else ""))
        print("    %-56s %6g  <- total" % ("", t["total"]))
        print()

    print("Totals: %s" % ", ".join("table %d = %g" % (i, t["total"])
                                   for i, t in enumerate(tables)))
    for line in reconcile(tables):
        print("  " + line)
    print("\nPick the table that is the estimate of record:")
    print('  python estimate.py record "<project>" --from "%s" --table N'
          % os.path.basename(path))
    return 0


# ---------------------------------------------------------------- the record

def record_path(project):
    folder = project if os.path.isabs(project) else os.path.join(ROOT, project)
    return os.path.join(folder, ".claude-context", "estimate.json"), folder


def load(project):
    p, _f = record_path(project)
    if not os.path.isfile(p):
        return None
    return json.loads(io.open(p, encoding="utf-8").read())


def save(project, rec):
    p, folder = record_path(project)
    if not os.path.isdir(folder):
        raise SystemExit("no project folder: %s" % folder)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps(rec, indent=2, ensure_ascii=False) + "\n")
    return p


def cmd_record(args, flags):
    project = args[0] if args else ""
    if not project:
        return fail("which project?")
    src = flags.get("from")
    rec = {
        "project": project,
        "label": flags.get("label", os.path.basename(project.rstrip("/\\"))),
        "source": flags.get("source") or (os.path.basename(src) if src else ""),
        "dated": flags.get("dated", ""),
        "recorded": date.today().isoformat(),
        "window": {"from": flags.get("dated", ""), "to": flags.get("to", "")},
        "items": [],
        "quoted_cost": flags.get("cost", ""),
        "notes": [],
    }
    if not rec["dated"]:
        return fail("--dated YYYY-MM-DD is required: an estimate with no date "
                    "cannot be compared against a window of work")

    if src:
        if "table" not in flags:
            return fail("--table N is required with --from. Run "
                        "`estimate.py read` first and pick one; this does not "
                        "guess which number in a scope document is the estimate")
        tables = hours_tables(docx_tables(src))
        n = int(flags["table"])
        if n < 0 or n >= len(tables):
            return fail("no table %d; the file has %d" % (n, len(tables)))
        rec["items"] = tables[n]["items"]
        rec["from_table"] = n
        others = [t["total"] for i, t in enumerate(tables) if i != n]
        if others:
            rec["notes"].append(
                "Other tables in the same document total %s hour(s); if they "
                "do not reconcile with this one, settle which is right."
                % ", ".join("%g" % o for o in others))
    elif "hours" in flags:
        rec["items"] = [{"task": flags.get("for", "whole project"),
                         "hours": float(flags["hours"]), "cost": None,
                         "note": "recorded by hand, not from a document",
                         "approved": None}]
    else:
        return fail("give either --from <file> --table N, or --hours H")

    p = save(project, rec)
    total = sum(i["hours"] for i in rec["items"])
    print("recorded %d item(s), %g hour(s) quoted, dated %s"
          % (len(rec["items"]), total, rec["dated"]))
    print("  %s" % p)
    print("\nNothing is approved yet, and compare will not run until it is - "
          "an estimate for work the client never signed off is not a miss.")
    print('  python estimate.py approve "%s" --all' % project)
    return 0


def cmd_approve(args, flags):
    project = args[0] if args else ""
    rec = load(project)
    if not rec:
        return fail("no estimate recorded for %s" % project)
    changed = 0
    for it in rec["items"]:
        if "all" in flags:
            it["approved"] = True
            changed += 1
        elif flags.get("item") and flags["item"].lower() in it["task"].lower():
            it["approved"] = True
            changed += 1
        elif flags.get("drop") and flags["drop"].lower() in it["task"].lower():
            it["approved"] = False
            changed += 1
    if not changed:
        return fail("nothing matched. Items are:\n  "
                    + "\n  ".join(i["task"] for i in rec["items"]))
    save(project, rec)
    yes = [i for i in rec["items"] if i["approved"] is True]
    no = [i for i in rec["items"] if i["approved"] is False]
    undecided = [i for i in rec["items"] if i["approved"] is None]
    print("%d item(s) changed. approved %d (%g h), not approved %d, undecided %d"
          % (changed, len(yes), sum(i["hours"] for i in yes), len(no),
             len(undecided)))
    return 0


# --------------------------------------------------------------- comparing

def actual_hours(label, start, end):
    """Hours from timespent, and the labels it knows, so a typo is visible."""
    projects, _raw, _kept = timespent.measure(start, end)
    if label not in projects:
        return None, sorted(projects)
    return projects[label]["sec"] / 3600.0, sorted(projects)


CAVEAT = """
How to read this
----------------
Actual hours are session time measured from the transcripts: the time a Claude
session was actively running on this work, with forked-session duplicates
removed and any gap over 30 minutes treated as a break.

It is a floor for hands-on time - work in the Lovable editor, in wp-admin, on
calls and in email is not in it - except where a long build ran while the
session idled, which inflates it instead. So the gap above is an indication,
not an invoice, and a difference under about 20% is inside the method's own
error."""


def compare_one(rec, start, end):
    yes = [i for i in rec["items"] if i["approved"] is True]
    undecided = [i for i in rec["items"] if i["approved"] is None]
    if undecided:
        return None, ("%d item(s) are still undecided, so there is nothing "
                      "meaningful to compare against:\n  "
                      % len(undecided)
                      + "\n  ".join(i["task"] for i in undecided))
    if not yes:
        return None, "no item was approved, so no work was quoted for."
    est = sum(i["hours"] for i in yes)
    act, known = actual_hours(rec["label"], start, end)
    if act is None:
        return None, ("no measured work under the label %r.\n"
                      "A label that matches nothing would read as "
                      "'came in 100%% under', so this stops instead. "
                      "Known labels:\n  %s" % (rec["label"], "\n  ".join(known)))
    return {"estimated": round(est, 2), "actual": round(act, 2),
            "ratio": round(act / est, 2) if est else None,
            "items": len(yes), "window": [start, end]}, None


def cmd_compare(args, flags):
    project = args[0] if args else ""
    rec = load(project)
    if not rec:
        return fail("no estimate recorded for %s. Record one with "
                    "`estimate.py record`." % project)
    start = flags.get("from") or rec["window"].get("from") or rec["dated"]
    end = flags.get("to") or rec["window"].get("to") or date.today().isoformat()

    print("# %s - quoted against actual\n" % rec["project"])
    print("estimate dated %s, from %s" % (rec["dated"], rec["source"] or "(by hand)"))
    print("window %s to %s\n" % (start, end))

    res, why = compare_one(rec, start, end)
    if not res:
        print(why)
        return 1

    print("%-22s %8.1f h" % ("quoted (approved)", res["estimated"]))
    print("%-22s %8.1f h" % ("actual (session)", res["actual"]))
    diff = res["actual"] - res["estimated"]
    print("%-22s %+8.1f h   %s" % ("difference", diff,
          "over" if diff > 0 else "under"))
    if res["ratio"]:
        print("%-22s %8.2fx" % ("actual / quoted", res["ratio"]))

    cost = rec.get("quoted_cost") or next(
        (i["cost"] for i in rec["items"] if i.get("cost")), "")
    money = MONEY.search(cost or "")
    if money:
        amount = float(re.sub(r"[^0-9.]", "", money.group(1)))
        sym = money.group(1)[0]
        print("\nquoted %s for %.1f h = %s%.2f an hour"
              % (money.group(1), res["estimated"], sym,
                 amount / max(res["estimated"], 0.01)))
        print("earned at the actual %.1f h = %s%.2f an hour"
              % (res["actual"], sym, amount / max(res["actual"], 0.01)))

    for n in rec.get("notes") or []:
        print("\nNote: %s" % n)
    print(CAVEAT)
    return 0


def cmd_calibrate(args, flags):
    rows = []
    for name in sorted(os.listdir(ROOT)):
        folder = os.path.join(ROOT, name)
        if not os.path.isdir(folder) or name.startswith("."):
            continue
        rec = load(name)
        if not rec:
            continue
        start = rec["window"].get("from") or rec["dated"]
        end = rec["window"].get("to") or date.today().isoformat()
        res, why = compare_one(rec, start, end)
        rows.append((name, res, why))

    print("# Estimate against actual, every project with a record\n")
    if not rows:
        print("No project has a recorded estimate yet, so there is nothing to "
              "calibrate. Record one when a quote goes out - that is the half "
              "of this that cannot be reconstructed later.")
        return 1

    usable = [(n, r) for n, r, _w in rows if r and r.get("ratio")]
    print("%-28s %9s %9s %8s" % ("Project", "Quoted", "Actual", "Ratio"))
    print("-" * 58)
    for name, res, why in rows:
        if res and res.get("ratio"):
            print("%-28s %7.1f h %7.1f h %7.2fx"
                  % (name[:28], res["estimated"], res["actual"], res["ratio"]))
        else:
            print("%-28s %s" % (name[:28], (why or "").splitlines()[0]))
    print("-" * 58)

    if len(usable) < MIN_PROJECTS:
        print("\n%d project(s) with a usable comparison. Under %d that is an "
              "anecdote, not a calibration, so no multiplier is given here."
              % (len(usable), MIN_PROJECTS))
        print("The rows above are still worth reading one at a time.")
        return 0

    ratios = sorted(r["ratio"] for _n, r in usable)
    mid = len(ratios) // 2
    median = ratios[mid] if len(ratios) % 2 else (ratios[mid - 1] + ratios[mid]) / 2
    print("\nmedian %.2fx across %d project(s), range %.2fx to %.2fx"
          % (median, len(ratios), ratios[0], ratios[-1]))
    print("Median, not mean: one runaway project would drag a mean and tell "
          "you nothing about the next quote.")
    print(CAVEAT)
    return 0


def cmd_list(args, flags):
    found = 0
    for name in sorted(os.listdir(ROOT)):
        if not os.path.isdir(os.path.join(ROOT, name)) or name.startswith("."):
            continue
        rec = load(name)
        if not rec:
            continue
        found += 1
        yes = [i for i in rec["items"] if i["approved"] is True]
        und = [i for i in rec["items"] if i["approved"] is None]
        print("%-28s %6g h quoted, %g h approved, %d undecided, dated %s"
              % (name[:28], sum(i["hours"] for i in rec["items"]),
                 sum(i["hours"] for i in yes), len(und), rec["dated"]))
    if not found:
        print("No estimates recorded yet.")
    return 0


def fail(msg):
    print(msg)
    return 2


def parse(argv):
    args, flags, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            key = a[2:]
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                flags[key] = argv[i + 1]
                i += 1
            else:
                flags[key] = True
        else:
            args.append(a)
        i += 1
    return args, flags


CMDS = {"read": cmd_read, "record": cmd_record, "approve": cmd_approve,
        "compare": cmd_compare, "calibrate": cmd_calibrate, "list": cmd_list}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        return 2
    args, flags = parse(sys.argv[2:])
    return CMDS[sys.argv[1]](args, flags)


if __name__ == "__main__":
    sys.exit(main())
