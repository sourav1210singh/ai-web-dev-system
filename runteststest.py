# -*- coding: utf-8 -*-
"""Does the runner find every suite, and refuse to lose one quietly?

    python runteststest.py

The runner's whole job is to be trusted, so the cases that matter are the ones
where it could be wrong without saying so: a suite it fails to discover, a
suite that exits non-zero while printing a full count, and a README figure it
calls current when it is not.

The discovery tests run against a real temporary tree with real files, and one
case runs a real generated suite through the real subprocess path. Discovery
and parsing can both look correct on strings and still not execute anything.
"""
import io
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import runtests as R  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:120] + "]") if extra else ""))


# The exact lines the two kinds of suite print, assembled rather than quoted
# whole, so this file does not become a suite by talking about one.
PY_LINE = 'print("\\n%s checks passed" %% (passed, len(RESULTS)))' % "%d/%d"
JS_LINE = "console.log(`\\n${pass}/${RESULTS.length} checks passed`);"

# ----------------------------------------------------------- parse_count
ok("a python suite's own output parses",
   R.parse_count("...\n\n97/97 checks passed") == (97, 97))
ok("a failing count parses as it is, not as a pass",
   R.parse_count("12/97 checks passed") == (12, 97))
ok("the last count wins, not the first",
   R.parse_count("1/1 checks passed\nlater: 97/97 checks passed") == (97, 97),
   "a suite that prints a sub-total first must not be read as one check")
ok("output with no count at all is None",
   R.parse_count("VERIFY: all checks passed") is None,
   "this is exactly verify.py, which has nothing to sum")
ok("empty output is None", R.parse_count("") is None)

# -------------------------------------------------------- looks_like_suite
ok("a python suite is recognised by its print line",
   R.looks_like_suite("x = 1\n" + PY_LINE))
ok("a js suite is recognised by its template literal",
   R.looks_like_suite("const x = 1;\n" + JS_LINE))
ok("a comment naming the pattern is NOT a suite",
   not R.looks_like_suite('# we look for "%s checks passed" in a file'
                          % "%d/%d"),
   "the first version of this matched its own explanation")
ok("the marker printed with no count is NOT a counted suite",
   not R.looks_like_suite('print("VERIFY: all checks passed")'),
   "nothing to add up")
ok("a docstring quoting the whole print line is still not a suite",
   not R.looks_like_suite('"""Each suite prints %s checks passed."""'
                          % "%d/%d"),
   "no print call on that line")
ok("a file that never mentions the marker is not a suite",
   not R.looks_like_suite("print('all done')"))

# -------------------------------------------------------------- the README
ok("the README figure parses through its comma",
   R.readme_claim("**1,191 checks across 27 test suites, all passing**")
   == (1191, 27))
ok("a figure with no comma parses too",
   R.readme_claim("994 checks across 22 test suites") == (994, 22))
ok("a README with no figure is None",
   R.readme_claim("no numbers here") is None)

# ------------------------------------------------------------- the verdict
ok("all green and current is 0", R.verdict([], False) == 0)
ok("a failed suite is 1", R.verdict([{"suite": "x"}], False) == 1)
ok("green but a stale README is 2", R.verdict([], True) == 2,
   "distinguishable, because one is broken code and one is a wrong number")
ok("a failure outranks a stale README", R.verdict([{"suite": "x"}], True) == 1)

# ------------------------------------------------- discovery, on real files
tmp = tempfile.mkdtemp(prefix="runtests-")
try:
    def put(rel, text):
        p = os.path.join(tmp, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8", newline="\n").write(text)
        return p

    put("a/atest.py", "RESULTS=[1]\npassed=1\n" + PY_LINE + "\n")
    put("a/btest.py", "RESULTS=[1]\npassed=1\n" + PY_LINE + "\n")
    put("b/ctest.js", "const RESULTS=[1], pass=1;\n" + JS_LINE + "\n")
    put("talksabout.py", '# prints "%s checks passed" when done' % "%d/%d")
    put("quiet.py", 'print("VERIFY: all checks passed")')
    put("node_modules/dep/dtest.py", PY_LINE)
    put("vendor/axe.min.js", JS_LINE)
    put("notcode.md", "%s checks passed" % "%d/%d")

    found, mentioned = R.discover(tmp)
    ok("every real suite is found", sorted(found)
       == ["a/atest.py", "a/btest.py", "b/ctest.js"], found)
    ok("a file that only talks about the marker is listed, not run",
       "talksabout.py" in mentioned, mentioned)
    ok("a file that prints the marker with no count is listed too",
       "quiet.py" in mentioned,
       "this is verify.py's shape, and it must not vanish")
    ok("nothing is silently dropped: found + mentioned covers every mention",
       len(found) + len(mentioned) == 5, (found, mentioned))
    ok("node_modules is skipped", not any("node_modules" in f for f in found))
    ok("a vendored library is skipped",
       not any("vendor" in f for f in found + mentioned),
       "a bundled axe-core is not a suite of ours")
    ok("a markdown file is never a suite",
       not any(f.endswith(".md") for f in found + mentioned))

    groups = R.group_by_dir(found)
    ok("suites sharing a folder are grouped, so they cannot run together",
       sorted(groups["a"]) == ["a/atest.py", "a/btest.py"], groups)
    ok("different folders are separate groups, so they can", len(groups) == 2,
       list(groups))

    # ------------------------------------------- the real subprocess path
    put("real/realtest.py",
        "RESULTS=[1,1,1]\npassed=3\n" + PY_LINE + "\n")
    r = R.run_one("real/realtest.py", tmp, 60)
    ok("a generated suite really runs and its count is read",
       r["ok"] and (r["passed"], r["total"]) == (3, 3), r)

    put("bad/badtest.py",
        "RESULTS=[1,1,1]\npassed=1\n" + PY_LINE + "\nimport sys\n"
        "sys.exit(1)\n")
    r = R.run_one("bad/badtest.py", tmp, 60)
    ok("a suite that fails is reported failed", not r["ok"], r["ok"])
    ok("and its real numbers are kept, not zeroed",
       (r["passed"], r["total"]) == (1, 3), (r["passed"], r["total"]))

    put("liar/liartest.py",
        "RESULTS=[1,1]\npassed=2\n" + PY_LINE + "\nimport sys\n"
        "sys.exit(3)\n")
    r = R.run_one("liar/liartest.py", tmp, 60)
    ok("a full count with a non-zero exit is still a failure", not r["ok"],
       "the exit code is evidence too, not just the printed line")

    r = R.run_one("real/missing.py", tmp, 60)
    ok("a suite that cannot be run is a failure, not a skip", not r["ok"],
       r["code"])

    # ---------------------------------------------- fix_readme, in a copy
    rd = os.path.join(tmp, "README.md")
    io.open(rd, "w", encoding="utf-8", newline="\n").write(
        "intro\n\n**1,191 checks across 27 test suites, all passing**, plus\n"
        "a verifier. 1,191 is also mentioned here.\n")
    keep, R.HERE = R.HERE, tmp
    try:
        stale, note = R.check_readme(1191, 27)
        ok("a matching README is not stale", stale is False, note)
        stale, note = R.check_readme(1250, 28)
        ok("a drifted README is stale", stale is True)
        ok("the message gives both the claim and the measurement",
           "1,191" in note and "1,250" in note and "28" in note, note)
        ok("fix_readme writes the measured figure", R.fix_readme(1250, 28))
        after = io.open(rd, encoding="utf-8").read()
        ok("the figure is now the measured one",
           "1,250 checks across 28 test suites" in after)
        ok("only the stated total is rewritten, not every number on the page",
           "1,191 is also mentioned here" in after,
           "a blind replace would have changed the prose too")
        ok("and the README now reads as current",
           R.check_readme(1250, 28)[0] is False)
    finally:
        R.HERE = keep
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# ------------------------------------------------------- the tools table
tmp2 = tempfile.mkdtemp(prefix="runtools-")
try:
    os.makedirs(os.path.join(tmp2, "skills", "one"))
    os.makedirs(os.path.join(tmp2, "skills", "one", "vendor"))
    for rel in ["install.py", "leakcheck.py", "runtests.py",
                "skills/one/alpha.py", "skills/one/beta.js",
                "skills/one/alphatest.py", "skills/one/vendor/lib.min.js",
                "runteststest.py", "installtest.py"]:
        io.open(os.path.join(tmp2, rel.replace("/", os.sep)), "w",
                encoding="utf-8").write("x")

    tools = R.count_tools(tmp2)
    ok("tools are the runnable scripts, by basename",
       tools == {"install.py", "leakcheck.py", "runtests.py", "alpha.py",
                 "beta.js"}, sorted(tools))
    ok("a test suite is not a tool", "alphatest.py" not in tools)
    ok("the runner's own test suite is not a tool",
       "runteststest.py" not in tools and "installtest.py" not in tools)
    ok("a vendored library one folder deeper is not a tool",
       "lib.min.js" not in tools,
       "this is the mistake that counted 27 tools instead of 26")

    doc = ("## The tools\n\n| Tool | What |\n|---|---|\n"
           "| `alpha.py` | a |\n| `beta.js` | b |\n| `install.py` | c |\n"
           "| `leakcheck.py` | d |\n| `runtests.py` | e |\n\n"
           "## The principles\n")
    rows, claims = R.readme_tools("system: 5 tools,\n" + doc
                                  + "\nIn daily use: 5 tools and four hooks.")
    ok("the table's rows are read off the markdown", len(rows) == 5, rows)
    ok("both claimed counts are found", claims == [5, 5], claims)
    ok("a count is found whatever the sentence around it says",
       R.readme_tools("it ships 9 tools.\n## The tools\n\n## The principles")[1]
       == [9],
       "requiring 'and N tools' meant a reworded sentence turned the check off")

    keep, R.HERE = R.HERE, tmp2
    try:
        io.open(os.path.join(tmp2, "README.md"), "w", encoding="utf-8",
                newline="\n").write("and 5 tools,\n" + doc
                                    + "\n5 tools and four hooks\n")
        bad, note = R.check_tools(tmp2)
        ok("a table that matches the disk is current", bad is False, note)

        io.open(os.path.join(tmp2, "skills", "one", "gamma.py"), "w",
                encoding="utf-8").write("x")
        bad, note = R.check_tools(tmp2)
        ok("a tool built but never listed is caught", bad is True)
        ok("and it is named, not just counted", "gamma.py" in note, note)
        ok("the wrong prose count is reported with the right one",
           "claims 5 and 5, there are 6" in note, note)
    finally:
        R.HERE = keep
finally:
    shutil.rmtree(tmp2, ignore_errors=True)

# ------------------------------------------------- one definition of paths
ok("the workspace is taken from the installer, not written again",
   R.WORKSPACE == R.install.WORKSPACE
   and R.CTX_INSTALLED == R.install.CTX_DST,
   "two definitions would disagree about where the context system is")
ok("the verifier is run from the installed copy, never from this repo",
   os.path.normpath(R.CTX_INSTALLED) != os.path.normpath(
       os.path.join(HERE, "context-system")),
   "the context tools write their logs beside themselves")

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
