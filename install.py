# -*- coding: utf-8 -*-
"""Make this system work on the machine it has been cloned onto.

Master copies live beside this file. Claude Code loads skills from
~/.claude/skills/ and hooks from ~/.claude/settings.json, neither of which is
tied to a Claude account, so everything here follows the machine and survives
signing in as somebody else.

    python install.py            show what would happen
    python install.py --apply    copy, verifying each file by checksum
    python install.py --status   what is installed right now
    python install.py --gate on|off   turn the claim gate on or off
    python install.py --apply --no-hooks   skills only, leave settings.json alone
    python install.py --rules [--apply]   put the working rules into every
                                 folder that is already a project

Three things are installed: the skills and agents, the context system that
records each session beside the projects, and the four hooks that run them.
Every path is worked out from where this file actually is, so a clone to
another machine or another folder needs no editing.
"""
import hashlib, io, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "skills")
DST = os.path.join(os.path.expanduser("~"), ".claude", "skills")
AGENT_SRC = os.path.join(HERE, "agents")
AGENT_DST = os.path.join(os.path.expanduser("~"), ".claude", "agents")

# The workspace is the folder this system sits in: the one that holds the
# client projects, the context files and the memory.
WORKSPACE = os.path.dirname(HERE)
CTX_SRC = os.path.join(HERE, "context-system")
CTX_DST = os.path.join(WORKSPACE, ".context-system")

# Skill documents quote absolute commands so they can be run as printed. The
# folder they were written in is not the folder they will be read in, so the
# path is rewritten as each file is copied. On the machine they were authored
# on this changes nothing.
AUTHORED_ROOT = b"C:\\Claude-Code"
REWRITE_EXT = (".md",)

# What the context system is made of. Anything else beside it is
# something it wrote, and belongs to the machine it wrote it on.
CTX_CODE = (".py", ".cmd", ".md")


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def md5_bytes(b):
    h = hashlib.md5()
    h.update(b)
    return h.hexdigest()


def rewrite(data, rel):
    """The authored root swapped for the real one, in files that quote it."""
    if not rel.lower().endswith(REWRITE_EXT):
        return data
    root = WORKSPACE.encode("utf-8")
    return data if root == AUTHORED_ROOT else data.replace(AUTHORED_ROOT, root)


def copy_verified(src, dstf, rel, bad):
    """Copy, rewriting paths, and check what landed is what was intended."""
    d = os.path.dirname(dstf)
    if not os.path.isdir(d):
        os.makedirs(d)
    with open(src, "rb") as a:
        data = rewrite(a.read(), rel)
    with open(dstf, "wb") as b:
        b.write(data)
    if md5(dstf) != md5_bytes(data):
        bad.append(dstf)
        return False
    return True


def install_context(bad):
    """The context system, which lives beside the projects, not inside here.

    Only the code is replaced. Whatever it has written there - the audit, the
    logs, the session routes, the worklog - is left exactly as it is, because
    that is the history this system exists to keep.
    """
    if not os.path.isdir(CTX_SRC):
        return 0
    n = 0
    # The top level, then one level of subdirectory. worklog/ lived only in the
    # installed copy for weeks: untracked, unpublished, and one machine move
    # from being gone, which is precisely what this installer exists to stop.
    for rel in sorted(os.listdir(CTX_SRC)):
        at = os.path.join(CTX_SRC, rel)
        if os.path.isdir(at):
            for f in sorted(os.listdir(at)):
                sub = os.path.join(at, f)
                if not os.path.isfile(sub) or not f.lower().endswith(CTX_CODE):
                    continue
                if copy_verified(sub, os.path.join(CTX_DST, rel, f),
                                 rel + "/" + f, bad):
                    n += 1
            continue
        if not os.path.isfile(at):
            continue
        # Code only, never data. Running one of these tools from inside the
        # repo leaves its log beside it, and copying that over the installed
        # one would replace a real history with a stub - the same install
        # that is meant to keep the history would be what destroyed it.
        if not rel.lower().endswith(CTX_CODE):
            continue
        if copy_verified(at, os.path.join(CTX_DST, rel), rel, bad):
            n += 1
    # The working rules travel WITH the context system rather than being read
    # out of the repo each time, so the recorder keeps putting them into
    # project folders even if the repo is moved or removed. Same mechanism as
    # the code: copied, checksum verified, replaced when it changes.
    tpl = os.path.join(HERE, "templates", "CLAUDE.md")
    if os.path.isfile(tpl) and copy_verified(
            tpl, os.path.join(CTX_DST, "rules.md"), "rules.md", bad):
        n += 1
    return n


def project_folders():
    """Folders that are already projects, by their own evidence.

    A folder with a context directory or a CLAUDE.md has been worked in. One
    without either has not, and giving it a rules file would be inventing a
    project that nobody started.
    """
    out = []
    for name in sorted(os.listdir(WORKSPACE)):
        folder = os.path.join(WORKSPACE, name)
        if not os.path.isdir(folder) or name.startswith("."):
            continue
        if os.path.isdir(os.path.join(folder, ".claude-context")) or \
                os.path.isfile(os.path.join(folder, "CLAUDE.md")):
            out.append(folder)
    return out


def install_rules(apply_it):
    """Put the working rules into every folder that is already a project.

    The recorder does this by itself from now on, but only when a folder is
    next worked in. Measured 11 Nov: the rules sat in 0 of 24 project folders
    because the template was built for a NEW project and nothing ever reached
    the ones that already existed. This is that one catch-up pass.
    """
    sys.path.insert(0, CTX_DST if os.path.isdir(CTX_DST) else CTX_SRC)
    import backfill
    body = backfill.rules_text().strip()
    if not body:
        print("rules: no template found, nothing to install")
        return 0
    done, already = [], 0
    for folder in project_folders():
        p = os.path.join(folder, "CLAUDE.md")
        before = backfill.read(p) if os.path.isfile(p) else ""
        if backfill.RULES_BEGIN in before:
            already += 1
            if not apply_it:
                continue
        if apply_it:
            backfill.install_rules_md(folder)
            if backfill.read(p) != before:
                done.append(os.path.basename(folder))
        else:
            done.append(os.path.basename(folder))
    verb = "updated" if apply_it else "would be given the rules"
    print("rules: %d folder(s) %s, %d already had the block"
          % (len(done), verb, already))
    for name in done:
        print("   %s" % name)
    if not apply_it:
        print("\nDRY RUN. Re-run with --rules --apply to write them.")
    return 0


def register_hooks():
    """Put the four hooks in ~/.claude/settings.json.

    Handed to the installer that already owns that file: it backs the settings
    up, merges by tag so hooks belonging to anything else survive, and writes
    the running interpreter's own path rather than a remembered one.
    """
    script = os.path.join(CTX_DST, "install_hooks.py")
    if not os.path.isfile(script):
        return "the context system is not installed, so no hooks were registered"
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", script],
                           capture_output=True, text=True, timeout=120)
    except Exception as e:
        return "hook registration could not run: %s" % e
    if p.returncode != 0:
        return "hook registration FAILED: %s" % (p.stderr or p.stdout)[-300:]
    return None


def hooks_registered():
    """Which of our hooks settings.json is actually carrying."""
    import json
    p = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    if not os.path.isfile(p):
        return []
    try:
        cfg = json.loads(io.open(p, encoding="utf-8").read() or "{}")
    except Exception:
        return []
    out = []
    for event, groups in (cfg.get("hooks") or {}).items():
        for g in groups or []:
            for h in (g.get("hooks") or []):
                if h.get("_tag") == "claude-context-system":
                    args = h.get("args") or []
                    out.append((event, os.path.basename(args[-1] if args else "?")))
    return sorted(out)


def skills():
    if not os.path.isdir(SRC):
        return []
    return sorted(d for d in os.listdir(SRC)
                  if os.path.isfile(os.path.join(SRC, d, "SKILL.md")))


def files_of(name):
    base = os.path.join(SRC, name)
    out = []
    for dp, dn, fn in os.walk(base):
        dn[:] = [x for x in dn if x not in ("__pycache__", "node_modules")]
        for f in fn:
            p = os.path.join(dp, f)
            out.append((p, os.path.relpath(p, base)))
    return out


def status():
    print("%-24s %-8s %s" % ("SKILL", "FILES", "INSTALLED AT ~/.claude/skills"))
    for s in skills():
        d = os.path.join(DST, s)
        here = len(files_of(s))
        there = sum(len(f) for _, _, f in os.walk(d)) if os.path.isdir(d) else 0
        same = "yes" if there else "NO"
        if there:
            same = "yes"
            for src, rel in files_of(s):
                dstf = os.path.join(d, rel)
                if not os.path.isfile(dstf) or md5(dstf) != md5(src):
                    same = "out of date"
                    break
        print("%-24s %-8d %s" % (s, here, same))
    print()
    print("master    : %s" % SRC)
    print("loaded    : %s" % DST)
    print("workspace : %s" % WORKSPACE)
    print("context   : %s%s" % (CTX_DST,
                                "" if os.path.isdir(CTX_DST) else "  NOT INSTALLED"))
    got = hooks_registered()
    if got:
        for event, script in got:
            print("hook      : %-13s %s" % (event, script))
    else:
        print("hook      : NONE REGISTERED. Run install.py --apply")


def gate(onoff):
    import json
    p = os.path.join(HERE, "gate.json")
    io.open(p, "w", encoding="utf-8", newline="\n").write(
        json.dumps({"enabled": onoff == "on"}, indent=1) + "\n")
    print("claim gate: %s  (%s)" % (onoff.upper(), p))
    if onoff == "off":
        print("Replies may now claim work is done without checking it.")
    return 0


def main():
    apply = "--apply" in sys.argv
    if "--gate" in sys.argv:
        i = sys.argv.index("--gate")
        v = sys.argv[i + 1] if len(sys.argv) > i + 1 else ""
        if v not in ("on", "off"):
            print("usage: install.py --gate on|off")
            return 1
        return gate(v)
    if "--rules" in sys.argv:
        return install_rules(apply)
    if "--status" in sys.argv:
        return status()
    names = skills()
    if not names:
        print("no skills found in %s" % SRC)
        return 1
    print("%-24s %s" % ("SKILL", "FILES"))
    for s in names:
        print("%-24s %d" % (s, len(files_of(s))))
    if not apply:
        print("\nDRY RUN. Re-run with --apply to install into %s" % DST)
        return 0

    bad, n = [], 0
    for s in names:
        target = os.path.join(DST, s)
        if os.path.isdir(target):
            shutil.rmtree(target)
        for src, rel in files_of(s):
            if copy_verified(src, os.path.join(target, rel), rel, bad):
                n += 1
    agents = 0
    if os.path.isdir(AGENT_SRC):
        if not os.path.isdir(AGENT_DST):
            os.makedirs(AGENT_DST)
        for f in sorted(os.listdir(AGENT_SRC)):
            if not f.endswith(".md"):
                continue
            if copy_verified(os.path.join(AGENT_SRC, f),
                             os.path.join(AGENT_DST, f), f, bad):
                agents += 1

    ctx = install_context(bad)

    if bad:
        print("\nCHECKSUM MISMATCH:")
        for b in bad:
            print("  - " + b)
        return 1
    print("\ninstalled %d file(s) across %d skill(s) and %d agent(s), "
          "all checksums match" % (n, len(names), agents))
    if ctx:
        print("context system: %d file(s) into %s" % (ctx, CTX_DST))

    if "--no-hooks" in sys.argv:
        print("hooks: left alone (--no-hooks)")
    else:
        why = register_hooks()
        if why:
            print("hooks: %s" % why)
        else:
            got = hooks_registered()
            print("hooks: %d registered in ~/.claude/settings.json (%s)"
                  % (len(got), ", ".join(sorted(set(e for e, _ in got)))))
    if WORKSPACE.encode("utf-8") != AUTHORED_ROOT:
        print("paths in the skill documents rewritten to %s" % WORKSPACE)
    print("Claude Code reads skills at session start, so they become available")
    print("in the NEXT session. Run `python install.py --status` to confirm.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main() or 0)
