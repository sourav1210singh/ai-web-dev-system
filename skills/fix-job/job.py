# -*- coding: utf-8 -*-
"""The fix job runner: state, parallel diagnosis, and a before/after diff.

    python job.py new <name> --domain <d> [--dir <project>] [--route <r>]
    python job.py diagnose <id>              # all checks at once, saved
    python job.py gate <id> --awaiting user-paste --note "prompt file path"
    python job.py resume <id>                # user has done their part
    python job.py verify <id>                # re-check, diff against before
    python job.py status [<id>] | list
    python job.py close <id> --summary "..."

What this does and does not do. It holds the state, runs the deterministic
checks in parallel, and diffs the result against the snapshot taken before the
change. It does not decide anything. Reading the project, writing the prompt,
judging a screenshot and talking to the client are Claude's work, and the
skill beside this file says how.

The gate stage exists because a Lovable prompt is never sent by Claude and a
WordPress session is opened by the user. The job waits there on purpose.
"""
import io, json, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)
CHECK = os.path.join(SKILLS, "launch-files", "check.py")
RQA = os.path.join(SKILLS, "responsive-qa", "rqa.js")
PARITY = os.path.join(SKILLS, "migration-parity", "parity.py")

# Each type runs its own checks and takes its own path. intake changes
# nothing, so it has no gate and no verify. golive refuses to close while a
# blocker is still standing, because that is the whole point of a launch gate.
JOB_TYPES = {
    "fix": {
        "stages": ["route", "read", "diagnose", "apply", "verify", "close"],
        "checks": ["launch", "responsive", "parity"],
        "gate": True, "strict": False,
        "what": "something on a live site is wrong and has to change",
    },
    "intake": {
        "stages": ["recon", "diagnose", "report", "close"],
        "checks": ["recon", "launch", "responsive"],
        "gate": False, "strict": False,
        "what": "a new client: find out what exists before touching anything",
    },
    "golive": {
        "stages": ["diagnose", "apply", "verify", "close"],
        "checks": ["launch", "responsive", "parity"],
        "gate": True, "strict": True,
        "what": "the launch gate: nothing ships with a blocker standing",
    },
}
ROUTES = ("lovable", "wordpress", "direct")


def spec(job):
    return JOB_TYPES.get(job.get("type") or "fix", JOB_TYPES["fix"])


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def jobs_dir(project):
    d = os.path.join(project, ".claude-context", "jobs")
    os.makedirs(d, exist_ok=True)
    return d


def find(job_id, project):
    p = os.path.join(jobs_dir(project), job_id + ".json")
    if not os.path.isfile(p):
        return None, p
    return json.loads(io.open(p, encoding="utf-8").read()), p


def save(job, path):
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(job, indent=1, ensure_ascii=False) + "\n")


def log(job, line):
    job.setdefault("history", []).append("%s  %s" % (now(), line))


# --- the deterministic checks, run together -----------------------------
def run_check(domain):
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", "-I", CHECK, domain],
                           capture_output=True, text=True, timeout=240)
        return p.stdout or p.stderr
    except Exception as e:
        return "check.py could not run: %s" % e


def run_rqa(url, out):
    if not os.path.isfile(RQA):
        return {"error": "rqa.js not found"}
    try:
        subprocess.run(["node", RQA, url, "--out", out],
                       capture_output=True, text=True, timeout=600)
    except Exception as e:
        return {"error": "rqa.js could not run: %s" % e}
    f = os.path.join(out, "findings.json")
    if not os.path.isfile(f):
        return {"error": "rqa.js produced no findings.json"}
    try:
        return json.loads(io.open(f, encoding="utf-8").read())
    except Exception as e:
        return {"error": "findings.json unreadable: %s" % e}


def run_recon(domain, out):
    """Everything discoverable about a domain, for an intake job.

    recon.py writes a report to --out and prints only progress to stdout, so
    the report has to be read from the file. Without --out it writes a
    recon-<domain> folder into the current directory, which on one run landed
    client data inside the published repository.
    """
    recon = os.path.join(SKILLS, "site-recon", "recon.py")
    if not os.path.isfile(recon):
        return "recon.py not found"
    try:
        subprocess.run([sys.executable, "-X", "utf8", "-I", recon, domain,
                        "--out", out], capture_output=True, text=True,
                       timeout=400)
    except Exception as e:
        return "recon.py could not run: %s" % e
    md = os.path.join(out, "recon.md")
    if not os.path.isfile(md):
        return "recon.py produced no report"
    try:
        return io.open(md, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return "recon report unreadable: %s" % e


def recon_facts(text):
    """The facts worth putting in front of a person, not the whole report.

    The report is markdown: `## Section` headings and `- **Key:** value`
    bullets. Anything that reads as a failure or a disagreement is kept too,
    because that is the part someone has to act on.
    """
    if not text or not text.lstrip().startswith("#"):
        return [text.strip()] if text and len(text) < 200 else []
    keep, section = [], ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            section = s[3:].split("(")[0].strip()
            continue
        m = re.match(r"^- \*\*(.+?):\*\*\s*(.*)$", s)
        if m:
            key, val = m.group(1), m.group(2)
            keep.append("%s%s: %s" % (section + " / " if section else "",
                                      key, val[:150]))
            continue
        if re.search(r"(?i)^- .*(failed|disagree|mismatch|not found|"
                     r"no .* record|expires)", s):
            keep.append("%s%s" % (section + " / " if section else "",
                                  s[2:][:150]))
    return keep[:30]


def launch_problems(text):
    """The lines in check.py output that are actually wrong."""
    bad = []
    for line in (text or "").splitlines():
        if re.search(r"(?i)MISSING|BLOCKED|WRONG DOMAIN|NOT A FILE|not set|"
                     r"^\s+favicon\s+0 bytes", line):
            bad.append(line.strip())
    return bad


def _rqa_rows(data):
    """Every finding, with the width it was seen at.

    rqa.js nests its findings per viewport. Reading only a top-level list
    silently reports a broken page as clean, which is worse than not checking
    at all, so every shape it can return is handled here.
    """
    if isinstance(data, list):
        return [(r.get("width", 0), r) for r in data if isinstance(r, dict)]
    rows = []
    for vp in (data.get("viewports") or []):
        if not isinstance(vp, dict):
            continue
        w = vp.get("width", 0)
        for r in (vp.get("findings") or []):
            if isinstance(r, dict):
                rows.append((w, r))
    for r in (data.get("findings") or []):
        if isinstance(r, dict):
            rows.append((r.get("width", 0), r))
    return rows


def rqa_problems(data):
    if isinstance(data, dict) and data.get("error"):
        return ["responsive QA: " + data["error"]]
    if isinstance(data, dict) and not data.get("viewports") \
            and not data.get("findings") and not data.get("counts"):
        return ["responsive QA: findings file had no results in it"]

    # the same fault shows at several widths; report it once with the widths
    grouped = {}
    for w, r in _rqa_rows(data):
        sev = str(r.get("sev") or r.get("severity") or "").upper()
        if sev not in ("BLOCKER", "MAJOR"):
            continue
        key = (sev, r.get("kind") or "", r.get("msg") or r.get("message") or "")
        grouped.setdefault(key, set()).add(int(w or 0))
    out = []
    for (sev, kind, msg), widths in sorted(grouped.items()):
        at = ", ".join("%dpx" % w for w in sorted(widths) if w)
        out.append("%s %s: %s%s" % (sev, kind or "finding", msg,
                                    ("  [%s]" % at) if at else ""))
    return out


def snapshot(job, label):
    """Run every check that applies, at the same time."""
    domain = job["domain"]
    url = domain if domain.startswith("http") else "https://" + domain
    out = os.path.join(job["project"], ".claude-context", "qa",
                       "%s-%s" % (job["id"], label))
    os.makedirs(out, exist_ok=True)

    wants = spec(job)["checks"]
    with ThreadPoolExecutor(max_workers=4) as ex:
        f_check = ex.submit(run_check, domain) if "launch" in wants else None
        f_rqa = ex.submit(run_rqa, url, out) if "responsive" in wants else None
        f_recon = (ex.submit(run_recon, domain, os.path.join(out, "recon"))
                   if "recon" in wants else None)
        f_par = None
        if "parity" in wants and job.get("old_url"):
            f_par = ex.submit(
                lambda: subprocess.run(
                    [sys.executable, "-X", "utf8", "-I", PARITY,
                     job["old_url"], url, "--out", out, "--quiet"],
                    capture_output=True, text=True, timeout=600).stdout)
        check_txt = f_check.result() if f_check else ""
        rqa_data = f_rqa.result() if f_rqa else None
        recon_txt = f_recon.result() if f_recon else ""
        par_txt = f_par.result() if f_par else ""

    snap = {
        "taken": now(),
        "launch": launch_problems(check_txt) if f_check else [],
        "responsive": rqa_problems(rqa_data) if f_rqa else [],
        "parity": [l.strip() for l in (par_txt or "").splitlines()
                   if l.strip().startswith("- ")][:20],
        "recon": recon_facts(recon_txt) if f_recon else [],
        "ran": [k for k in ("launch", "responsive", "parity", "recon")
                if k in wants],
        "qa_dir": out,
        "raw_launch": check_txt,
    }
    job.setdefault("snapshots", {})[label] = snap
    return snap


def blockers(snap):
    """Everything that should stop a launch."""
    return (snap.get("launch") or []) + (snap.get("responsive") or [])


def digest(snap, title):
    L = ["## %s  (%s)" % (title, snap["taken"]), ""]
    ran = snap.get("ran") or ["launch", "responsive", "parity"]
    if snap.get("recon"):
        L.append("**What the domain says about itself**")
        L += ["  " + r for r in snap["recon"][:24]]
        L.append("")
    for key, head in (("launch", "Launch files"),
                      ("responsive", "Responsive QA"),
                      ("parity", "Content parity")):
        if key not in ran:
            continue
        rows = snap.get(key) or []
        L.append("**%s** - %s" % (head, "clean" if not rows
                                  else "%d problem(s)" % len(rows)))
        L += ["  - " + r for r in rows[:12]]
        L.append("")
    L.append("Screenshots: %s" % snap["qa_dir"])
    L.append("")
    L.append("Read the screenshots before saying anything about how it looks.")
    return "\n".join(L)


# --- commands -----------------------------------------------------------
def cmd_new(a):
    project = os.path.abspath(a.get("dir") or os.getcwd())
    jid = re.sub(r"[^a-z0-9]+", "-", (a.get("name") or "fix").lower()).strip("-")
    jid = "%s-%s" % (jid[:28], time.strftime("%m%d%H%M"))
    jtype = (a.get("type") or "fix").lower()
    if jtype not in JOB_TYPES:
        print("type must be one of: %s" % ", ".join(sorted(JOB_TYPES)))
        return 2
    job = {"id": jid, "name": a.get("name") or jid, "domain": a["domain"],
           "project": project, "type": jtype, "route": a.get("route"),
           "old_url": a.get("old-url"),
           "stage": JOB_TYPES[jtype]["stages"][0],
           "awaiting": None, "created": now(), "history": [], "snapshots": {}}
    if job["route"] and job["route"] not in ROUTES:
        print("route must be one of: %s" % ", ".join(ROUTES))
        return 2
    log(job, "%s job opened for %s" % (jtype, job["domain"]))
    if job["route"] and jtype == "fix":
        job["stage"] = "read"
        log(job, "route set to %s" % job["route"])
    save(job, os.path.join(jobs_dir(project), jid + ".json"))
    print("job %s opened  (%s, %s)" % (jid, jtype, job["domain"]))
    print("%s" % JOB_TYPES[jtype]["what"])
    print("stages: %s" % " -> ".join(JOB_TYPES[jtype]["stages"]))
    print("stage: %s" % job["stage"])
    if jtype == "fix":
        print("\nnext: establish the route from evidence, then")
    elif jtype == "intake":
        print("\nintake changes nothing. It reads, and it reports.")
    else:
        print("\nnext: measure before anything ships")
    print("  python job.py diagnose %s --dir \"%s\"" % (jid, project))
    return 0


def cmd_diagnose(a):
    project = os.path.abspath(a.get("dir") or os.getcwd())
    job, path = find(a["id"], project)
    if not job:
        print("no job %s in %s" % (a["id"], path))
        return 2
    sp = spec(job)
    print("running %s together...\n" % ", ".join(sp["checks"]))
    snap = snapshot(job, "before")
    log(job, "diagnosed: %d launch, %d responsive, %d parity"
        % (len(snap["launch"]), len(snap["responsive"]), len(snap["parity"])))
    print(digest(snap, "Before"))

    if job.get("type") == "intake":
        job["stage"] = "report"
        save(job, path)
        print("\nstage: report. Nothing here changes anything.")
        print("Write up the facts, the risks, and the short list of what has")
        print("to come from the client. Then:")
        print("  python job.py close %s --summary \"...\"" % job["id"])
        return 0

    job["stage"] = "apply"
    save(job, path)
    if sp["strict"]:
        standing = blockers(snap)
        print("\n%d blocker(s) standing. Nothing ships until these are gone."
              % len(standing) if standing else
              "\nNothing is blocking a launch on these checks.")
    print("\nstage: apply. Lovable and WordPress stop at the gate:")
    print("  python job.py gate %s --awaiting user-paste --note \"<file>\""
          % job["id"])
    return 0


def cmd_gate(a):
    project = os.path.abspath(a.get("dir") or os.getcwd())
    job, path = find(a["id"], project)
    if not job:
        print("no job %s" % a["id"])
        return 2
    job["awaiting"] = a.get("awaiting") or "user"
    job["awaiting_note"] = a.get("note") or ""
    job["stage"] = "apply"
    log(job, "waiting on the user: %s %s" % (job["awaiting"],
                                             job["awaiting_note"]))
    save(job, path)
    print("job %s is waiting on you: %s" % (job["id"], job["awaiting"]))
    if job["awaiting_note"]:
        print("  %s" % job["awaiting_note"])
    print("\nwhen that is done:  python job.py resume %s" % job["id"])
    return 0


def cmd_resume(a):
    project = os.path.abspath(a.get("dir") or os.getcwd())
    job, path = find(a["id"], project)
    if not job:
        print("no job %s" % a["id"])
        return 2
    job["awaiting"] = None
    job["stage"] = "verify"
    log(job, "user confirmed their part; verifying")
    save(job, path)
    print("job %s resumed, stage: verify" % job["id"])
    print("  python job.py verify %s" % job["id"])
    return 0


def cmd_verify(a):
    project = os.path.abspath(a.get("dir") or os.getcwd())
    job, path = find(a["id"], project)
    if not job:
        print("no job %s" % a["id"])
        return 2
    before = (job.get("snapshots") or {}).get("before")
    snap = snapshot(job, "after")
    job["stage"] = "close"
    save(job, path)
    print(digest(snap, "After"))

    if not before:
        print("No before snapshot, so there is nothing to compare against.")
        return 1
    print("## What changed\n")
    worse = False
    for key, head in (("launch", "Launch files"),
                      ("responsive", "Responsive QA"),
                      ("parity", "Content parity")):
        b, af = set(before.get(key) or []), set(snap.get(key) or [])
        fixed, new = sorted(b - af), sorted(af - b)
        print("**%s**" % head)
        for r in fixed:
            print("  FIXED  %s" % r)
        for r in new:
            print("  NEW    %s" % r)
            worse = True
        if not fixed and not new:
            print("  no change")
        print("")
    log(job, "verified: %s" % ("new problems appeared" if worse else "no regressions"))
    save(job, path)
    if worse:
        print("Something is worse than before. Fix that before closing.")
        return 1
    print("Nothing regressed. Look at the screenshots, then close:")
    print("  python job.py close %s --summary \"...\"" % job["id"])
    return 0


def cmd_close(a):
    project = os.path.abspath(a.get("dir") or os.getcwd())
    job, path = find(a["id"], project)
    if not job:
        print("no job %s" % a["id"])
        return 2
    # a launch gate that closes over a standing blocker is not a gate
    if spec(job)["strict"]:
        snaps = job.get("snapshots") or {}
        latest = snaps.get("after") or snaps.get("before")
        standing = blockers(latest) if latest else []
        if standing and not a.get("force"):
            print("This is a golive job and %d blocker(s) are still standing:"
                  % len(standing))
            for r in standing[:10]:
                print("  - %s" % r)
            print("\nFix them and run verify again. If this is going out")
            print("anyway as someone's decision, record that decision and")
            print("pass --force, so the file says it was a choice.")
            return 1

    job["stage"] = "closed"
    job["summary"] = a.get("summary") or ""
    if a.get("force"):
        log(job, "CLOSED OVER STANDING BLOCKERS by explicit decision")
    log(job, "closed: %s" % job["summary"])
    save(job, path)
    print("job %s closed" % job["id"])
    print("Record it in CLIENT-LOG.md and reply to the client.")
    return 0


def cmd_status(a):
    project = os.path.abspath(a.get("dir") or os.getcwd())
    d = jobs_dir(project)
    ids = [a["id"]] if a.get("id") else \
        [f[:-5] for f in sorted(os.listdir(d)) if f.endswith(".json")]
    if not ids:
        print("no jobs in %s" % d)
        return 0
    for jid in ids:
        job, _p = find(jid, project)
        if not job:
            continue
        print("%-34s %-9s %-10s %s" % (
            job["id"], job.get("stage"), job.get("route") or "-",
            ("WAITING: " + job["awaiting"]) if job.get("awaiting") else ""))
        if a.get("id"):
            print("  domain: %s" % job["domain"])
            for h in job.get("history", []):
                print("    %s" % h)
    return 0


def parse_args(argv):
    out, i = {}, 0
    pos = []
    while i < len(argv):
        t = argv[i]
        if t.startswith("--"):
            k = t[2:]
            v = argv[i + 1] if i + 1 < len(argv) and \
                not argv[i + 1].startswith("--") else "true"
            out[k] = v
            i += 2 if v != "true" else 1
        else:
            pos.append(t)
            i += 1
    return pos, out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    pos, flags = parse_args(rest)
    a = dict(flags)
    if cmd == "new":
        a["name"] = pos[0] if pos else "fix"
        if not a.get("domain"):
            print("new needs --domain")
            return 2
        return cmd_new(a)
    if cmd in ("list", "status"):
        a["id"] = pos[0] if pos else None
        return cmd_status(a)
    if not pos:
        print("%s needs a job id" % cmd)
        return 2
    a["id"] = pos[0]
    fn = {"diagnose": cmd_diagnose, "gate": cmd_gate, "resume": cmd_resume,
          "verify": cmd_verify, "close": cmd_close}.get(cmd)
    if not fn:
        print(__doc__)
        return 2
    return fn(a)


if __name__ == "__main__":
    sys.exit(main())
