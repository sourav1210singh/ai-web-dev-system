# -*- coding: utf-8 -*-
"""Make the skills in this folder available to every Claude Code session here.

Master copies live in C:\\Claude-Code\\.ai-system\\skills\\ so they travel with
the folder and survive an account switch. Claude Code loads skills from
~/.claude/skills/, so this copies them there.

    python install.py            show what would happen
    python install.py --apply    copy, verifying each file by checksum
    python install.py --status   what is installed right now
    python install.py --gate on|off   turn the claim gate on or off
"""
import hashlib, io, os, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "skills")
DST = os.path.join(os.path.expanduser("~"), ".claude", "skills")
AGENT_SRC = os.path.join(HERE, "agents")
AGENT_DST = os.path.join(os.path.expanduser("~"), ".claude", "agents")


def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


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
    print("master : %s" % SRC)
    print("loaded : %s" % DST)


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
            dstf = os.path.join(target, rel)
            d = os.path.dirname(dstf)
            if not os.path.isdir(d):
                os.makedirs(d)
            want = md5(src)
            with open(src, "rb") as a, open(dstf, "wb") as b:
                b.write(a.read())
            if md5(dstf) != want:
                bad.append(dstf)
            else:
                n += 1
    agents = 0
    if os.path.isdir(AGENT_SRC):
        if not os.path.isdir(AGENT_DST):
            os.makedirs(AGENT_DST)
        for f in sorted(os.listdir(AGENT_SRC)):
            if not f.endswith(".md"):
                continue
            src, dstf = os.path.join(AGENT_SRC, f), os.path.join(AGENT_DST, f)
            want = md5(src)
            with open(src, "rb") as a, open(dstf, "wb") as b:
                b.write(a.read())
            if md5(dstf) != want:
                bad.append(dstf)
            else:
                agents += 1

    if bad:
        print("\nCHECKSUM MISMATCH:")
        for b in bad:
            print("  - " + b)
        return 1
    print("\ninstalled %d file(s) across %d skill(s) and %d agent(s), "
          "all checksums match" % (n, len(names), agents))
    print("Claude Code reads skills at session start, so they become available")
    print("in the NEXT session. Run `python install.py --status` to confirm.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main() or 0)
