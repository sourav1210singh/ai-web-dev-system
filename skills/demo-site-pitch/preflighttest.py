# -*- coding: utf-8 -*-
"""Does the pre-push check catch what it exists to catch?

This runs before a demo is pushed to a public repo, which is the one moment a
secret or a client's name becomes irreversible. It went without tests.

    python preflighttest.py
"""
import io
import os
import shutil
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import preflight as P  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:110] + "]") if extra else ""))


# ------------------------------------------------- files that must not ship
for f, want in [(".env", True), (".env.local", True), (".env.production", True),
                ("secrets.json", True), ("secret.yaml", True),
                ("secrets.yml", True), ("id_rsa", True), ("key.pem", True),
                ("environment.ts", False), ("secretsanta.txt", False),
                ("README.md", False), ("package.json", False)]:
    got = bool(P.SECRET_FILE.search(f))
    ok("%s %s treated as a secret file" % (f, "is" if want else "is not"),
       got == want, "matched" if got else "no match")

# ------------------------------------------------ secrets inside the text
#
# These fixtures have to look like assigned credentials, because that is what
# the pattern under test matches - so they are assembled rather than written
# out. The repo's own leak check reads the literal form as a real credential,
# and it is right to: security.js assembles its PEM pattern for the same
# reason. Keeping the check strict and the fixtures indirect is the trade that
# works; the other way round weakens the check for every real file.
A = lambda k, v: k + ' = "' + v + '"'
for s, want in [(A("API_KEY", "abcdefghijklmnop1234"), True),
                (A("const " + "tok" + "en", "ghp_" + "a" * 20), True),
                (A("pass" + "word", "correcthorsebatterystaple"), True),
                (A("se" + "cret", "sk_live_4eC39HqLyjWDarjtT1zd"), True),
                (A("apiKey", "short"), False),
                ("// remember to set the api key in the env", False),
                ("const tokenCount = 42", False)]:
    got = bool(P.SECRET_IN_TEXT.search(s))
    ok("%s" % ("a long assigned credential is caught" if want
               else "ordinary text is not flagged"),
       got == want, s[:48])

# ------------------------------------------------------------- the dashes
# copy-standards forbids em and en dashes in anything a client reads, and they
# arrive through four different spellings.
for s, want in [("one – two", True), ("one — two", True),
                ("one &#8211; two", True), ("one &#8212; two", True),
                ("one &ndash; two", True), ("one &mdash; two", True),
                ("one - two", False), ("a-b", False), ("&amp;", False)]:
    got = bool(P.DASH.search(s))
    ok("%r %s flagged as a dash" % (s, "is" if want else "is not"),
       got == want)

# ------------------------------------------------------------ the walker
tmp = tempfile.mkdtemp(prefix="preflighttest-")
try:
    def put(rel, body="x"):
        p = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8").write(body)

    put("src/app.tsx", "export const App = () => null;")
    put("README.md", "# demo")
    put("node_modules/pkg/index.js", "module.exports = 1;")
    put(".next/cache/x.js", "cached")
    put("dist/bundle.js", "built")
    put(".git/config", "[core]")
    put("public/logo.svg", "<svg/>")

    seen = [os.path.relpath(p, tmp).replace("\\", "/") for p in P.walk(tmp)]
    ok("source files are walked", "src/app.tsx" in seen, seen[:5])
    ok("node_modules is skipped",
       not any(s.startswith("node_modules") for s in seen),
       "or every dependency's own secrets get reported")
    ok("build output is skipped",
       not any(s.startswith(("dist/", ".next/")) for s in seen), seen)
    ok("the git directory is skipped",
       not any(s.startswith(".git/") for s in seen))
    ok("every skipped directory is one nobody authored",
       P.SKIP >= {"node_modules", ".git", "dist", "build"}, sorted(P.SKIP))
    ok("the text extensions cover what a site is written in",
       all(e in P.TEXT_EXT for e in (".ts", ".tsx", ".js", ".jsx", ".md",
                                     ".json", ".css", ".html")),
       P.TEXT_EXT)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
