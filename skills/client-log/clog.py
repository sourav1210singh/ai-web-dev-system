# -*- coding: utf-8 -*-
"""Client log - file what the client gave or said, so it can be found later.

  clog.py add <project> --what "..." [--from NAME] [--via email|whatsapp|call|
       upwork|lovable|meeting] [--date YYYY-MM-DD] [--kind ask|decision|asset|
       approval|complaint|info] [--files PATH ...] [--note "..."]

  clog.py search <project> <term> [<term> ...]
  clog.py list <project> [--open]        open items only

Files are copied (never moved) into
<project>\\.claude-context\\client-log\\<date>-<slug>\\ and verified by checksum.
The ledger is <project>\\.claude-context\\CLIENT-LOG.md, append only.
"""
import argparse, datetime, hashlib, io, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"C:\Claude-Code"
KINDS = ("ask", "decision", "asset", "approval", "complaint", "info")


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def slug(s, n=46):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return (s[:n].strip("-") or "entry")


def find_project(name):
    if os.path.isdir(name) and os.path.isabs(name):
        return name
    for d in os.listdir(ROOT):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p) and d.lower() == name.lower():
            return p
    for d in os.listdir(ROOT):
        p = os.path.join(ROOT, d)
        if os.path.isdir(p) and name.lower() in d.lower():
            return p
    return None


def ledger(project):
    return os.path.join(project, ".claude-context", "CLIENT-LOG.md")


def ensure_ledger(project):
    p = ledger(project)
    if not os.path.isfile(p):
        d = os.path.dirname(p)
        if not os.path.isdir(d):
            os.makedirs(d)
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            "# Client log - %s\n\n"
            "Everything the client gave or said, in date order, with the files\n"
            "filed beside it. Append only; never rewrite an entry.\n\n"
            "An entry records what was ASKED. It is not evidence that anything\n"
            "was delivered. Verify against the live site before telling the\n"
            "client something is done.\n\n---\n\n"
            % os.path.basename(project))
    return p


def cmd_add(a):
    project = find_project(a.project)
    if not project:
        print("no such project folder: %s" % a.project)
        return 1
    date = a.date or datetime.date.today().isoformat()
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        print("date must be YYYY-MM-DD")
        return 1

    stored = []
    if a.files:
        dest = os.path.join(project, ".claude-context", "client-log",
                            "%s-%s" % (date, slug(a.what)))
        os.makedirs(dest, exist_ok=True)
        for f in a.files:
            if not os.path.isfile(f):
                print("  missing file, skipped: %s" % f)
                continue
            target = os.path.join(dest, os.path.basename(f))
            i = 1
            while os.path.exists(target) and md5(target) != md5(f):
                stem, ext = os.path.splitext(os.path.basename(f))
                target = os.path.join(dest, "%s-%d%s" % (stem, i, ext))
                i += 1
            want = md5(f)
            shutil.copy2(f, target)
            if md5(target) != want:
                print("  CHECKSUM MISMATCH: %s" % target)
                return 1
            stored.append((os.path.relpath(target, project).replace("\\", "/"),
                           os.path.getsize(target), f))

    p = ensure_ledger(project)
    L = ["## %s - %s" % (date, a.what.strip()), ""]
    meta = []
    if a.frm:
        meta.append("**From:** %s" % a.frm)
    if a.via:
        meta.append("**Via:** %s" % a.via)
    meta.append("**Type:** %s" % (a.kind or "info"))
    meta.append("**Status:** open")
    L.append(" · ".join(meta))
    L.append("")
    if a.note:
        L.append(a.note.strip())
        L.append("")
    if stored:
        L.append("Files filed here:")
        L.append("")
        for rel, size, src in stored:
            L.append("- `%s` (%s KB, from `%s`)" % (rel, size // 1024 or 1, src))
        L.append("")
    L.append("---")
    L.append("")
    io.open(p, "a", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")

    print("logged to %s" % os.path.relpath(p, ROOT))
    for rel, _s, _f in stored:
        print("  filed: %s" % rel)
    if not stored and a.files:
        print("  (no files were copied)")
    return 0


def entries(project):
    txt = io.open(ledger(project), encoding="utf-8").read() if \
        os.path.isfile(ledger(project)) else ""
    out = []
    for block in re.split(r"(?=^## \d{4}-\d{2}-\d{2})", txt, flags=re.M):
        if block.startswith("## "):
            out.append(block.rstrip())
    return out


def cmd_search(a):
    project = find_project(a.project)
    if not project:
        print("no such project folder: %s" % a.project)
        return 1
    terms = [t.lower() for t in a.terms]
    hits = [b for b in entries(project)
            if all(t in b.lower() for t in terms)]
    print("%d of %d entries match %s\n" % (len(hits), len(entries(project)),
                                           " + ".join(a.terms)))
    for b in hits:
        print(b)
        print()
    return 0


def cmd_list(a):
    project = find_project(a.project)
    if not project:
        print("no such project folder: %s" % a.project)
        return 1
    es = entries(project)
    if a.open:
        es = [b for b in es if "**Status:** open" in b]
    for b in es:
        head = b.splitlines()[0][3:]
        status = "open" if "**Status:** open" in b else "closed"
        print("  %-6s %s" % (status, head[:100]))
    print("\n%d entr%s" % (len(es), "y" if len(es) == 1 else "ies"))
    return 0


def main():
    ap = argparse.ArgumentParser(add_help=True, description=__doc__)
    sub = ap.add_subparsers(dest="cmd")

    p1 = sub.add_parser("add")
    p1.add_argument("project")
    p1.add_argument("--what", required=True)
    p1.add_argument("--from", dest="frm")
    p1.add_argument("--via")
    p1.add_argument("--date")
    p1.add_argument("--kind", choices=KINDS)
    p1.add_argument("--note")
    p1.add_argument("--files", nargs="*")

    p2 = sub.add_parser("search")
    p2.add_argument("project")
    p2.add_argument("terms", nargs="+")

    p3 = sub.add_parser("list")
    p3.add_argument("project")
    p3.add_argument("--open", action="store_true")

    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "add":
        return cmd_add(a)
    if a.cmd == "search":
        return cmd_search(a)
    if a.cmd == "list":
        return cmd_list(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
