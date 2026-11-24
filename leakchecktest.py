# -*- coding: utf-8 -*-
"""Does the pre-push leak check actually catch a leak, and stay quiet otherwise?

This is the gate that runs before every push, and it had failed twice in two
days with nothing testing it:

  23 Nov: its workspace root was hard-coded, so on any other machine the client
          list read empty, nothing could match, and it printed CLEAN having
          compared the repo against nothing.
  24 Nov: a deliverables folder called "reports" at the workspace root turned
          the ordinary English word into a client term, and it produced 103
          findings, every one of them false.

Those are the two ways a check like this dies: it stops seeing, or it cries
wolf. Both are pinned below, against a throwaway workspace that looks like the
real one, with the real script copied into it and run as a subprocess.

**No leak string is written literally in this file.** Every fixture secret is
assembled at runtime from pieces, because leakcheck.py runs over this
repository and a test that seeds a fake private key in its own source makes
the gate report itself. A detector finding its own test fixtures is a real
failure here and has happened before.
"""
import io, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
RESULTS = []

CLIENT_ONE = "Kronofex"              # single word, becomes one term
CLIENT_TWO = "Zephyr Dynamics"       # two words, phrase only
GENERIC_FOLDER = "reports"           # ours, must never become a term


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def secrets():
    """The fixture secrets, built from parts so none of them exists as a
    literal in this file. Reversed, joined or repeated: anything but typed."""
    return {
        "public ip": ".".join(["8", "8", "8", "8"]),
        "private key": "-----BEGIN " + "RSA " + "PRIVATE" + " KEY" + "-----",
        "credential": "api" + "_key" + " = " + '"' + ("A1b2C3d4" * 3) + '"',
        "bearer": "Bear" + "er " + ("z" * 26),
        "home path": "C:" + chr(92) + "Users" + chr(92) + "someone" + chr(92),
        "email": "jane" + chr(64) + "clientmail" + ".com",
        "supabase": ("q" * 20) + "." + "supabase" + ".co",
    }


def quiet():
    """Things that look like secrets and are not. Each one is a rule the
    script states, so each one has to hold."""
    return {
        "private range": ".".join(["10", "0", "0", "5"]),
        "documentation range": ".".join(["192", "0", "2", "44"]),
        "test net three": ".".join(["203", "0", "113", "9"]),
        "reserved email": "someone" + chr(64) + "example" + ".com",
        "retina image": "logo" + chr(64) + "2x" + ".png",
        "ordinary word": "This tool reports what it measured.",
        "one word of a phrase": "Zephyr alone is not the client.",
    }


def build(root, with_leaks):
    """A throwaway workspace shaped like the real one."""
    repo = os.path.join(root, ".ai-system")
    os.makedirs(repo, exist_ok=True)
    shutil.copy2(os.path.join(HERE, "leakcheck.py"),
                 os.path.join(repo, "leakcheck.py"))

    for name in (CLIENT_ONE, CLIENT_TWO, GENERIC_FOLDER):
        os.makedirs(os.path.join(root, name), exist_ok=True)

    # a domain and a platform, both in a project memory
    mem = os.path.join(root, CLIENT_ONE, ".claude-context", "memory")
    os.makedirs(mem, exist_ok=True)
    io.open(os.path.join(mem, "notes.md"), "w", encoding="utf-8").write(
        "Site is https://kronofexgroup.com and it is built on "
        "https://webflow.com\n")

    io.open(os.path.join(repo, ".gitignore"), "w", encoding="utf-8").write(
        "ignored.md\n")

    # always present, and must never be reported
    body = ["# Notes", ""] + list(quiet().values())
    io.open(os.path.join(repo, "clean.md"), "w", encoding="utf-8",
            newline="\n").write("\n".join(body) + "\n")

    # a file git would never carry, holding a real-looking secret
    io.open(os.path.join(repo, "ignored.md"), "w", encoding="utf-8").write(
        secrets()["private key"] + "\n")

    if with_leaks:
        lines = ["# Draft", ""]
        lines.append("We rebuilt the %s homepage." % CLIENT_ONE)
        lines.append("Then %s approved it." % CLIENT_TWO)
        lines.append("Their site is kronofexgroup.com")
        lines += list(secrets().values())
        io.open(os.path.join(repo, "draft.md"), "w", encoding="utf-8",
                newline="\n").write("\n".join(lines) + "\n")

        # A client name split by a line break, in a file of its own and
        # nowhere else in it. Kept separate on purpose: with the same name
        # also sitting on one line in draft.md, the assertion would pass off
        # that line and prove nothing about the whole-file pass.
        io.open(os.path.join(repo, "wrapped.md"), "w", encoding="utf-8",
                newline="\n").write(
            "The work was signed off by Zephyr\nDynamics last week.\n")
    return repo


def run(repo, *args):
    p = subprocess.run([PY, "-X", "utf8", os.path.join(repo, "leakcheck.py")]
                       + list(args), capture_output=True, text=True,
                       timeout=300)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tmp = tempfile.mkdtemp(prefix="leakchecktest_")
    try:
        # ---------------------------------------------- it reads real inputs
        repo = build(tmp, with_leaks=True)
        rc, out = run(repo, "--list")
        m = re.search(r"(\d+) terms checked", out)
        count = int(m.group(1)) if m else 0
        ok("it says how many client terms it checked", bool(m), out[:70])
        ok("and that number is not zero", count > 0,
           "%d terms" % count)
        ok("a client folder name became a term",
           "kronofex" in out.lower(), out[-120:])
        ok("a domain from a project memory became a term",
           "kronofexgroup" in out.lower(), out[-120:])

        # ------------------------------------------------- it stays quiet
        ok("a folder of ours is not a client",
           GENERIC_FOLDER not in out.lower().split(), out[-120:])
        ok("a platform named in a memory is not a client",
           "webflow" not in out.lower(), out[-120:])
        ok("one ordinary word of a two word client is not a term by itself",
           not re.search(r"\bzephyr\b(?!\s)", out.lower()) or
           "zephyr dynamics" in out.lower(), out[-120:])

        # ------------------------------------------------- it finds leaks
        rc, out = run(repo)
        ok("a file with leaks exits non-zero", rc == 1, "rc=%d" % rc)
        found = out.lower()
        for label in ("client name 'kronofex'", "private key", "credential",
                      "bearer token", "public ipv4", "home path",
                      "personal email", "supabase ref"):
            ok("it reports %s" % label, label in found,
               "" if label in found else out[-200:])
        ok("it finds the two word client as a phrase",
           "zephyr dynamics" in found, "")
        wrapped = [l for l in out.splitlines() if "wrapped.md" in l]
        ok("it finds a client name broken across a line break",
           any("zephyr dynamics" in l.lower() for l in wrapped),
           "; ".join(wrapped)[:110] or "wrapped.md never reported")

        # ----------------------------------------- and does not cry wolf
        for label in ("10.0.0.5", "192.0.2.44", "203.0.113.9"):
            ok("%s is not reported as a public address" % label,
               label not in out, out[-160:])
        ok("a reserved example address is not a personal email",
           "someone@example.com" not in out)
        ok("a retina image name is not an email", "logo@2x" not in out)
        ok("the ordinary word 'reports' is not a finding",
           "client name 'reports'" not in found)
        ok("it never reports clean.md", "clean.md" not in out, out[-160:])

        # --------------------------------------------------- mechanics
        ok("a gitignored file is not scanned", "ignored.md" not in out,
           out[-160:])
        ok("it does not scan itself", "leakcheck.py:" not in out, out[-160:])
        m = re.search(r"checked (\d+) file", out)
        ok("it says how many files it read", bool(m) and int(m.group(1)) > 0,
           m.group(0) if m else out[:70])

        # ------------------------------------------------- a clean tree
        shutil.rmtree(tmp, ignore_errors=True)
        tmp = tempfile.mkdtemp(prefix="leakchecktest_")
        repo = build(tmp, with_leaks=False)
        rc, out = run(repo)
        ok("a tree with nothing to find exits zero", rc == 0, "rc=%d" % rc)
        ok("and says so plainly", "CLEAN" in out, out[-160:])
        m = re.search(r"against (\d+) client term", out)
        ok("a clean result still names how much it checked against",
           bool(m) and int(m.group(1)) > 0, m.group(0) if m else out[:70])

        # ------------------------------- a workspace with nothing to check
        # The quietest way for this gate to die. A fresh clone sits in a
        # workspace with no client folders, so the term list is empty, every
        # file matches nothing, and the old code called that CLEAN and exited
        # zero. Measured on 24 Nov: it did exactly that.
        shutil.rmtree(tmp, ignore_errors=True)
        tmp = tempfile.mkdtemp(prefix="leakchecktest_")
        bare = os.path.join(tmp, ".ai-system")
        os.makedirs(bare)
        shutil.copy2(os.path.join(HERE, "leakcheck.py"),
                     os.path.join(bare, "leakcheck.py"))
        io.open(os.path.join(bare, "a.md"), "w", encoding="utf-8").write(
            "nothing of interest here\n")
        rc, out = run(bare)
        ok("no client folders is not a pass", rc != 0, "rc=%d" % rc)
        ok("and it does not call that clean", "CLEAN" not in out, out[-160:])
        ok("it says which half of the check did not run",
           "client name half" in out, out[-160:])
        ok("and it still says it checked keys and paths",
           "Keys, addresses" in out, out[-160:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
