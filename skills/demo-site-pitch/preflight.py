# -*- coding: utf-8 -*-
"""Pre-flight for a demo site before it goes to GitHub and Vercel.

    python preflight.py <project-dir> [--repo <name>] [--user <github-user>]

Checks the things that embarrass you in front of a client or leak a secret,
then prints the exact commands for this project, with the names filled in.
Changes nothing.
"""
import json, os, re, subprocess, sys

SECRET_FILE = re.compile(r"(?i)^\.env($|\.)|secrets?\.(json|ya?ml)$|\.pem$|_rsa$")
SECRET_IN_TEXT = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|passwd)\b\s*[=:]\s*['\"]?"
    r"[A-Za-z0-9_\-\.]{16,}")
DASH = re.compile(r"[–—]|&#821[12];|&[mn]dash;")
SKIP = {"node_modules", ".next", ".git", "dist", "build", ".vercel",
        "__pycache__", "out", "coverage"}
TEXT_EXT = (".ts", ".tsx", ".js", ".jsx", ".mdx", ".md", ".json", ".css",
            ".html", ".txt")


def run(cmd, cwd=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           timeout=300, shell=isinstance(cmd, str))
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return 1, str(e)


def walk(root):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            yield os.path.join(dp, f)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    proj = os.path.abspath(sys.argv[1])
    if not os.path.isdir(proj):
        print("no such folder: %s" % proj)
        return 1
    name = os.path.basename(proj)
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    def arg(k, d):
        return sys.argv[sys.argv.index("--" + k) + 1] if "--" + k in sys.argv else d
    repo = arg("repo", re.sub(r"-", "_", slug.title().replace("-", "_")))
    user = arg("user", "<github-user>")
    alias = "github-" + slug
    key = os.path.join(os.path.expanduser("~"), ".ssh", slug.replace("-", "_") + "_deploy")

    ok, warn, fail = [], [], []
    have_remote = [False]
    sys.stdout.reconfigure(encoding="utf-8")

    # ---- project shape
    pkg = os.path.join(proj, "package.json")
    if os.path.isfile(pkg):
        d = json.loads(open(pkg, encoding="utf-8").read() or "{}")
        ok.append("package.json found: %s" % ", ".join(sorted(d.get("dependencies", {}))[:7]))
        if "build" not in d.get("scripts", {}):
            fail.append("package.json has no build script - Vercel will not know what to run")
    else:
        warn.append("no package.json - a static site is fine, but Vercel needs a framework preset")

    gi = os.path.join(proj, ".gitignore")
    if not os.path.isfile(gi):
        fail.append(".gitignore is MISSING - node_modules and .env would be committed")
    else:
        g = open(gi, encoding="utf-8", errors="replace").read()
        for must in ("node_modules", ".env"):
            if must not in g:
                fail.append(".gitignore does not cover %s" % must)
        if ".env" in g and "node_modules" in g:
            ok.append(".gitignore covers node_modules and .env")

    # ---- secrets
    leaked, dashes = [], []
    for f in walk(proj):
        base = os.path.basename(f)
        rel = os.path.relpath(f, proj)
        if SECRET_FILE.match(base):
            leaked.append(rel + "  (file itself)")
            continue
        if not f.lower().endswith(TEXT_EXT):
            continue
        try:
            t = open(f, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if SECRET_IN_TEXT.search(t):
            leaked.append(rel)
        if f.lower().endswith((".ts", ".tsx", ".js", ".jsx", ".mdx", ".md", ".html")):
            for ln in t.splitlines():
                if not DASH.search(ln):
                    continue
                st = ln.strip()
                # a dash inside a code comment is invisible to the visitor
                if st.startswith(("//", "/*", "*", "<!--", "#")):
                    continue
                m = DASH.search(ln)
                snip = ln[max(0, m.start() - 28):m.end() + 28].strip()
                dashes.append((rel, snip))
                break

    tracked = []
    rc, out = run(["git", "ls-files"], cwd=proj)
    if rc == 0:
        tracked = [x.strip().replace("/", os.sep) for x in out.splitlines() if x.strip()]
    for l in leaked:
        p0 = l.split("  (")[0]
        if not tracked or p0 in tracked:
            fail.append("possible secret: %s" % l)
        else:
            warn.append("possible secret, not tracked by git: %s" % l)
    if not leaked:
        ok.append("no obvious secret in the tree")

    if dashes:
        fail.append("em/en dash in visible content, %d file(s):" % len(dashes))
        for rel, snip in dashes[:6]:
            fail.append("    %s  ->  %s" % (rel, snip[:70]))
    else:
        ok.append("no em or en dash in visible content")

    # ---- git
    if not os.path.isdir(os.path.join(proj, ".git")):
        warn.append("not a git repository yet")
    else:
        rc, out = run(["git", "status", "--porcelain"], cwd=proj)
        if out.strip():
            warn.append("%d uncommitted change(s)" % len(out.strip().splitlines()))
        else:
            ok.append("working tree clean")
        rc, out = run(["git", "remote", "-v"], cwd=proj)
        if out.strip():
            ok.append("remote: " + out.splitlines()[0])
            m = re.search(r"git@([\w.-]+):", out)
            if m and m.group(1) != "github.com":
                alias = m.group(1)
                have_remote[0] = True
            if m and m.group(1) == "github.com":
                warn.append("remote uses plain github.com - with more than one "
                            "GitHub account, use a per-project SSH alias instead")
        else:
            warn.append("no git remote set")

    # ---- build
    if os.path.isfile(pkg) and "--skip-build" not in sys.argv:
        print("running the production build, this takes a minute...\n")
        rc, out = run("npm run build", cwd=proj)
        if rc == 0:
            ok.append("production build passes")
        else:
            fail.append("BUILD FAILS - Vercel will fail the same way:\n      "
                        + "\n      ".join(out.strip().splitlines()[-6:]))

    # ---- report
    print("# Pre-flight - %s\n" % name)
    for t, items in (("FAIL", fail), ("CHECK", warn), ("OK", ok)):
        for i in items:
            print("  %-5s %s" % (t, i))
    print()

    if fail:
        print("Fix the FAIL items before pushing. Nothing was changed.\n")
    print("## Commands for this project\n")
    print("One-time, if this project has no key yet:")
    print('  ssh-keygen -t ed25519 -C "%s deploy" -f "%s"' % (slug, key))
    print("  # add the .pub as a Deploy Key on the repo (write access), then put")
    print("  # this in ~/.ssh/config:")
    print("""
  Host %s
    HostName github.com
    User git
    IdentityFile %s
    IdentitiesOnly yes
""" % (alias, key))
    print("  ssh -T git@%s          # must greet you by the right account\n" % alias)
    print("Push:")
    print("  cd \"%s\"" % proj)
    print("  git init -b main" if not os.path.isdir(os.path.join(proj, ".git")) else "  # already a repo")
    print("  git add -A && git commit -m \"<what changed, plain English>\"")
    if have_remote[0]:
        print("  # remote already set, nothing to add")
    else:
        print("  git remote add origin git@%s:%s/%s.git" % (alias, user, repo))
    print("  git push -u origin main\n")
    print("Then connect the repo in the Vercel dashboard (Add New > Project >")
    print("Import from GitHub). Framework is detected; no settings needed for")
    print("a standard Next.js app. Record the URL it gives you.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
