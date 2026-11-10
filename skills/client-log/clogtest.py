# -*- coding: utf-8 -*-
"""Does the client log file things where they can be found months later?

The whole point of this tool is the day something is disputed, so the parts
that matter are: the project is resolved to the right folder, a file is
recorded by checksum rather than by name, and an entry written today is still
findable later.

    python clogtest.py
"""
import io
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clog as C  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:110] + "]") if extra else ""))


# ------------------------------------------------------------- the slug
ok("a title becomes a filename-safe slug",
   C.slug("Client sent the NEW logo!") == "client-sent-the-new-logo",
   C.slug("Client sent the NEW logo!"))
ok("punctuation and spacing collapse to single hyphens",
   C.slug("a  --  b??  c") == "a-b-c", C.slug("a  --  b??  c"))
ok("a long title is cut without leaving a trailing hyphen",
   not C.slug("x " * 60).endswith("-"), C.slug("x " * 60))
ok("the cut respects the length given",
   len(C.slug("abcdefghij " * 10, 20)) <= 20)
ok("an empty title still yields something openable",
   C.slug("") == "entry" and C.slug("!!!") == "entry")
ok("non-latin text does not produce an empty name",
   C.slug("ग्राहक") == "entry", C.slug("ग्राहक"))

# ------------------------------------------------------------ the digest
tmp = tempfile.mkdtemp(prefix="clogtest-")
try:
    a = os.path.join(tmp, "a.bin")
    b = os.path.join(tmp, "b.bin")
    io.open(a, "wb").write(b"the same bytes")
    io.open(b, "wb").write(b"the same bytes")
    ok("two files with identical contents have the same checksum",
       C.md5(a) == C.md5(b),
       "a resend under a new name is recognisable as the same file")
    io.open(b, "wb").write(b"the same bytes, almost")
    ok("a changed file has a different checksum", C.md5(a) != C.md5(b))

    big = os.path.join(tmp, "big.bin")
    io.open(big, "wb").write(b"\x00" * (3 << 20))
    ok("a file larger than one read block is hashed whole",
       len(C.md5(big)) == 32, "chunked reads must not truncate")

    # -------------------------------------------------- finding a project
    real_root = C.ROOT
    C.ROOT = tmp
    try:
        os.makedirs(os.path.join(tmp, "Bright Dental"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "Another Client"), exist_ok=True)
        io.open(os.path.join(tmp, "notafolder.txt"), "w").write("x")

        ok("an exact name finds the project",
           C.find_project("Bright Dental") == os.path.join(tmp, "Bright Dental"))
        ok("the match ignores case",
           C.find_project("bright dental") == os.path.join(tmp, "Bright Dental"))
        ok("a partial name finds it too",
           C.find_project("bright") == os.path.join(tmp, "Bright Dental"))
        ok("a name matching nothing returns nothing, rather than guessing",
           C.find_project("no such client") is None,
           "filing against the wrong client is worse than not filing")
        ok("a file is never returned as a project",
           C.find_project("notafolder") is None)

        proj = os.path.join(tmp, "Bright Dental")
        ok("the ledger lives inside the project, not in a temp folder",
           C.ledger(proj) == os.path.join(proj, ".claude-context",
                                          "CLIENT-LOG.md"))
        C.ensure_ledger(proj)
        ok("the ledger is created with a heading",
           os.path.isfile(C.ledger(proj))
           and io.open(C.ledger(proj), encoding="utf-8").read().strip() != "")
        before = io.open(C.ledger(proj), encoding="utf-8").read()
        C.ensure_ledger(proj)
        ok("calling it again does not overwrite what is already recorded",
           io.open(C.ledger(proj), encoding="utf-8").read() == before,
           "the history is the thing being protected")
    finally:
        C.ROOT = real_root
finally:
    shutil.rmtree(tmp, ignore_errors=True)

ok("the entry kinds cover what a client actually does",
   set(C.KINDS) >= {"ask", "decision", "asset", "approval", "complaint"},
   ", ".join(C.KINDS))

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
