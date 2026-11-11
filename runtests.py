# -*- coding: utf-8 -*-
"""Run every test suite in this system, with one command, before a push.

    python runtests.py                 everything, then check the README
    python runtests.py --jobs 1        one suite at a time
    python runtests.py --only seo      only suites whose path contains "seo"
    python runtests.py --fix-readme    write the measured total into README.md
    python runtests.py --json

Why this exists. The README's test counts were wrong in four places and its
tool table had stood at 13 rows for three weeks, because measuring either of
them meant writing an ad-hoc shell loop by hand. A figure that takes a loop to
measure does not get measured, and then it is quoted anyway. This is that loop,
kept, with the README comparison on the end so the number cannot drift again
without saying so.

**Discovery is by content, not by filename.** Looking for `*test*.py` missed
`context-system/verify.py`, which is a suite and is not called test anything,
and that is how the 27th went unrun. Every counted suite does happen to be
named test-something today, so matching on the name would have found them all;
the rule should not depend on that holding for the next one.

Three kinds of thing are run, and they are not the same kind of evidence:

- **Counted suites**, each printing `N/N checks passed` against its own
  fixtures. Their numbers are summed, and that sum is the figure the README
  quotes.
- **The full-file verifier**, `context-system/verify.py`. It reads this
  machine's own context files rather than fixtures, so it is reported apart
  from the total and says so. On a fresh clone there is nothing to verify and
  it is skipped rather than failed.
- **`leakcheck.py`**, the pre-push check that no client name or credential has
  reached this repository.

Suites in the same folder are run one after another, never at the same time.
Three of them live in `skills/responsive-qa` and write their output beside
themselves, so running those together would have them overwrite each other.
Different folders run at the same time.

Two things in the README are then checked against what was just measured: the
total it quotes, and the tools table. The table is checked because the count in
the prose was wrong twice over and the table itself had stood at 13 rows while
14 more tools were built. A number nobody can re-derive in one command is a
number that drifts.

Exit codes: **0** all green and the README current, **1** something failed,
**2** everything passed but the README is out of date.
"""
import io
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import install  # noqa: E402  constants only, its main() is guarded

# One definition of where things are, taken from the installer rather than
# written again here, so the two cannot disagree about the workspace.
WORKSPACE = install.WORKSPACE
CTX_INSTALLED = install.CTX_DST

MARKER = "checks passed"
COUNT_RE = re.compile(r"(\d+)/(\d+)\s+" + MARKER)

# A counted suite is one that PRINTS a count with the marker. The count is the
# test, not the filename and not a list of names to skip, which is why
# context-system/verify.py is not picked up here: it prints the marker with no
# number, so there is nothing to sum. It is run by name further down, for a
# second reason as well, that it must run from the installed copy.
#
# Printing is also part of the test, because the first version of this matched
# its own comment explaining the pattern. The same shape of bug as a copy
# checker reporting the dash rule's own wording: a file that names the thing it
# detects. So the marker and the count have to sit on a line that calls print.
COUNT_FMT = r"(?:%d/%d|\}/\$\{[^}]*\})\s+"
PRINTS_COUNT = re.compile(r"^.*(?:print|console\.log)\s*\(.*" + COUNT_FMT
                          + MARKER, re.M)
README_RE = re.compile(r"([\d,]+)\s+checks across\s+(\d+)\s+test suites")
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "vendor", "templates"}
DEFAULT_TIMEOUT = 900


# --------------------------------------------------------------- pure parts

def parse_count(out):
    """(passed, total) from a suite's own last line, or None."""
    hits = COUNT_RE.findall(out or "")
    if not hits:
        return None
    a, b = hits[-1]
    return int(a), int(b)


def readme_claim(text):
    """(checks, suites) the README states, or None."""
    m = README_RE.search(text or "")
    if not m:
        return None
    return int(m.group(1).replace(",", "")), int(m.group(2))


def looks_like_suite(text):
    """A file is a counted suite if it prints a count with the marker.

    Mentioning the string is not enough, or this runner would find itself.
    Printing it without a number is not enough either, because there would be
    nothing to add up.
    """
    return bool(text) and bool(PRINTS_COUNT.search(text))


def discover(root):
    """(suites, mentions) under root, by content, as sorted relative paths.

    `mentions` is every other file that contains the marker without printing a
    count. They are listed in the report rather than dropped, because the one
    thing this runner must never do is let a suite go quiet: a suite that
    wrapped its print across two lines would otherwise simply stop being run,
    and the total would fall without anything saying so.
    """
    suites, mentions = [], []
    for dp, dn, fn in os.walk(root):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS)
        for f in sorted(fn):
            if not f.endswith((".py", ".js")):
                continue
            p = os.path.join(dp, f)
            try:
                text = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                continue
            if MARKER not in text:
                continue
            rel = os.path.relpath(p, root).replace("\\", "/")
            (suites if looks_like_suite(text) else mentions).append(rel)
    return suites, mentions


def group_by_dir(paths):
    """Folder -> its suites, in order. Suites sharing a folder share output
    paths, so they must not run at the same time as each other."""
    groups = {}
    for p in paths:
        groups.setdefault(os.path.dirname(p), []).append(p)
    return groups


def verdict(failed, stale):
    if failed:
        return 1
    if stale:
        return 2
    return 0


# ------------------------------------------------------------- running them

def run_one(rel, root, timeout):
    full = os.path.join(root, rel)
    d, b = os.path.dirname(full), os.path.basename(full)
    cmd = ([sys.executable, "-X", "utf8", b] if b.endswith(".py")
           else ["node", b])
    t0 = time.time()
    try:
        p = subprocess.run(cmd, cwd=d, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        code = p.returncode
    except subprocess.TimeoutExpired:
        out, code = "timed out after %ds" % timeout, -9
    except FileNotFoundError as e:
        out, code = "could not run: %s" % e, -1
    n = parse_count(out)
    ok = code == 0 and n is not None and n[0] == n[1]
    return {"suite": rel, "ok": ok, "passed": n[0] if n else 0,
            "total": n[1] if n else 0, "code": code,
            "secs": round(time.time() - t0, 1),
            "tail": "\n".join((out or "").strip().splitlines()[-12:])}


def run_group(suites, root, timeout):
    return [run_one(s, root, timeout) for s in suites]


def run_all(suites, root, jobs, timeout):
    groups = list(group_by_dir(suites).values())
    if jobs <= 1:
        return [r for g in groups for r in run_group(g, root, timeout)]
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        return [r for g in ex.map(lambda g: run_group(g, root, timeout),
                                  groups) for r in g]


def run_verifier(timeout):
    """The installed copy, never the one in this repo: the context tools write
    their logs beside themselves, and inside the repo that is a stray file."""
    p = os.path.join(CTX_INSTALLED, "verify.py")
    if not os.path.isfile(p):
        return {"name": "verify.py", "state": "skipped",
                "note": "the context system is not installed on this machine"}
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", "verify.py"],
                           cwd=CTX_INSTALLED, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return {"name": "verify.py", "state": "failed", "note": str(e)[:120]}
    if "projects=0" in out.replace(" ", ""):
        return {"name": "verify.py", "state": "skipped",
                "note": "no project context on this machine yet"}
    ok = r.returncode == 0 and "all checks passed" in out
    return {"name": "verify.py", "state": "ok" if ok else "failed",
            "note": (out.strip().splitlines() or [""])[-1][:120]}


def run_leakcheck(timeout):
    p = os.path.join(HERE, "leakcheck.py")
    if not os.path.isfile(p):
        return {"name": "leakcheck.py", "state": "skipped", "note": "absent"}
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", "leakcheck.py"],
                           cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return {"name": "leakcheck.py", "state": "failed", "note": str(e)[:120]}
    ok = r.returncode == 0 and "CLEAN" in out
    return {"name": "leakcheck.py", "state": "ok" if ok else "failed",
            "note": (out.strip().splitlines() or [""])[-1][:120]}


# ------------------------------------------------------------- the README

def check_readme(checks, suites):
    """Is the figure the README quotes still the measured one?"""
    p = os.path.join(HERE, "README.md")
    if not os.path.isfile(p):
        return None, "README.md not found"
    text = io.open(p, encoding="utf-8").read()
    claim = readme_claim(text)
    if claim is None:
        return None, "the README does not quote a total"
    if claim == (checks, suites):
        return False, "README is current: %s checks across %d suites" % (
            "{:,}".format(checks), suites)
    return True, ("README says %s checks across %d suites, measured %s "
                  "across %d" % ("{:,}".format(claim[0]), claim[1],
                                 "{:,}".format(checks), suites))


def count_tools(root):
    """The runnable scripts a person would call, by basename.

    Depth is the test: `skills/<name>/x.py` is a tool of ours and
    `skills/<name>/vendor/axe.min.js` is a bundled library, which is how a
    hand count of this once came out at 27 instead of 26. Test suites are not
    tools, and the runner is.
    """
    out = set()
    for f in os.listdir(root):
        if f.endswith(".py") and not f.endswith("test.py") \
                and f not in ("runteststest.py",):
            out.add(f)
    skills = os.path.join(root, "skills")
    if os.path.isdir(skills):
        for name in os.listdir(skills):
            d = os.path.join(skills, name)
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if f.endswith((".py", ".js")) and "test" not in f:
                    out.add(f)
    return out


def readme_tools(text):
    """(the table's rows, the counts the prose claims), both as given."""
    sec = text.split("## The tools")[-1].split("## The principles")[0]
    rows = set(re.findall(r"\|\s*`([A-Za-z0-9_.-]+\.(?:py|js))`\s*\|", sec))
    # Every "N tools" in the prose, whatever the sentence around it. The first
    # version wanted "and N tools" or "N tools and", which meant rewording the
    # sentence would have switched the check off without anything saying so.
    claims = [int(m) for m in re.findall(r"(\d+) tools\b", text)]
    return rows, claims


def check_tools(root):
    """Does the tools table still match the tools, and the count match both?"""
    p = os.path.join(HERE, "README.md")
    if not os.path.isfile(p):
        return None, "README.md not found"
    text = io.open(p, encoding="utf-8").read()
    real = count_tools(root)
    rows, claims = readme_tools(text)
    bad = []
    if rows != real:
        missing = sorted(real - rows)
        extra = sorted(rows - real)
        if missing:
            bad.append("not in the table: " + ", ".join(missing))
        if extra:
            bad.append("in the table but not on disk: " + ", ".join(extra))
    off = [c for c in claims if c != len(real)]
    if off:
        bad.append("the prose claims %s, there are %d"
                   % (" and ".join(str(c) for c in off), len(real)))
    if bad:
        return True, "; ".join(bad)
    return False, "tools table is current: %d tools, listed and counted" \
        % len(real)


def fix_readme(checks, suites):
    p = os.path.join(HERE, "README.md")
    text = io.open(p, encoding="utf-8").read()
    new = README_RE.sub("%s checks across %d test suites"
                        % ("{:,}".format(checks), suites), text, count=1)
    if new == text:
        return False
    io.open(p, "w", encoding="utf-8", newline="\n").write(new)
    return True


# ------------------------------------------------------------------- main

def main():
    argv = sys.argv[1:]
    as_json = "--json" in argv
    fix = "--fix-readme" in argv
    jobs = 4
    timeout = DEFAULT_TIMEOUT
    only = None
    for i, a in enumerate(argv):
        if a == "--jobs" and i + 1 < len(argv):
            jobs = max(1, int(argv[i + 1]))
        if a == "--only" and i + 1 < len(argv):
            only = argv[i + 1]
        if a == "--timeout" and i + 1 < len(argv):
            timeout = max(10, int(argv[i + 1]))

    suites, mentions = discover(HERE)
    if only:
        suites = [s for s in suites if only.lower() in s.lower()]
    if not suites:
        print("no suites found%s" % (" matching %r" % only if only else ""))
        return 1

    t0 = time.time()
    results = run_all(suites, HERE, jobs, timeout)
    results.sort(key=lambda r: r["suite"])
    ver = run_verifier(timeout)
    leak = run_leakcheck(timeout)

    checks = sum(r["passed"] for r in results if r["ok"])
    failed = [r for r in results if not r["ok"]]
    # The README counts the verifier as a suite alongside the counted ones.
    suite_total = len(results) + (1 if ver["state"] == "ok" else 0)

    stale, note = (None, "not checked (--only was used)") if only \
        else check_readme(checks, suite_total)
    tstale, tnote = (None, "not checked (--only was used)") if only \
        else check_tools(HERE)

    if as_json:
        import json
        print(json.dumps({"suites": results, "verifier": ver, "leak": leak,
                          "checks": checks, "suite_total": suite_total,
                          "mentions_not_run": mentions,
                          "readme_stale": stale, "readme": note,
                          "tools_stale": tstale, "tools": tnote,
                          "secs": round(time.time() - t0, 1)}, indent=1))
        return verdict(failed, stale or tstale)

    print("# Test suites\n")
    for r in results:
        print("%-5s %-44s %4d/%-4d %6.1fs"
              % ("ok" if r["ok"] else "FAIL", r["suite"], r["passed"],
                 r["total"], r["secs"]))
    print("-" * 70)
    print("%-5s %-44s %4d checks  %6.1fs"
          % ("", "%d counted suite(s)" % len(results), checks,
             round(time.time() - t0, 1)))
    print()
    print("%-5s %-44s %s" % (ver["state"], "verify.py (this machine's own "
                             "context)", ver["note"]))
    print("%-5s %-44s %s" % (leak["state"], "leakcheck.py (before every "
                             "push)", leak["note"]))
    if mentions:
        print()
        print("Mentions the marker, not counted (check this list is right):")
        for m in mentions:
            print("      %s" % m)
    print()
    print("README: %s" % note)
    print("Tools : %s" % tnote)

    if failed:
        print("\n%d suite(s) failed:" % len(failed))
        for r in failed:
            print("\n--- %s (exit %s)" % (r["suite"], r["code"]))
            print(r["tail"])
    elif stale and fix:
        if fix_readme(checks, suite_total):
            print("README updated to %s checks across %d suites."
                  % ("{:,}".format(checks), suite_total))
            stale = False
    elif stale:
        print("Run with --fix-readme to write the measured figure in.")

    if tstale:
        print("The tools table needs a row written by hand. --fix-readme "
              "does not invent descriptions.")

    if ver["state"] == "failed" or leak["state"] == "failed":
        failed = failed or [{"suite": "verify/leakcheck"}]

    return verdict(failed, stale or tstale)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
