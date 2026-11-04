# -*- coding: utf-8 -*-
"""Group sessions of a folder into projects, using evidence from the transcripts."""
import io, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ctxlib import slugify, oneline

HERE = os.path.dirname(os.path.abspath(__file__))
from ctxlib import ROOT
# Claude Code names a project directory after the working directory
# with its separators flattened, so this is the workspace spelled the
# same way: C:\Claude-Code becomes C--Claude-Code.
PREFIX = ROOT.replace(":", "-").replace("\\", "-").replace("/", "-")

# Which old session really belongs to which folder, what was recorded in the
# wrong place, which turns inside one thread were another client's work: all
# of that is this machine's own history, it names real clients, and none of
# it is reusable anywhere else. It lives in local_history.py beside this
# file, which is never published. A clone starts with none.
try:
    from local_history import OVERRIDES, RELOCATE, EXTRACT
except ImportError:
    OVERRIDES, RELOCATE, EXTRACT = {}, {}, []


def norm_sig(text):
    return " ".join(str(text or "").lower().split())[:120]


def group_folder(sessions):
    """sessions: inventory rows for one project_dir -> list of group dicts."""
    pdir = sessions[0]["project_dir"]
    groups = {}          # slug -> dict
    for r in sorted(sessions, key=lambda x: (x["first_ts"] or "")):
        title = r["custom_title"] or r["ai_title"] or "untitled"
        slug = slugify(title, "session-" + r["session_id"][:8])
        label = title
        ov = OVERRIDES.get((pdir, slug))
        if ov:
            slug, label = ov
        g = groups.setdefault(slug, {
            "slug": slug, "labels": {}, "sessions": [], "sigs": set()})
        g["labels"][label] = g["labels"].get(label, 0) + r["human_prompts"]
        g["sessions"].append(r)
        g["sigs"].add(norm_sig(r["first_prompt"]))

    # R2: merge groups that share an identical first-prompt signature (forks)
    merged = True
    while merged:
        merged = False
        keys = list(groups)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                if a not in groups or b not in groups:
                    continue
                if groups[a]["sigs"] & groups[b]["sigs"]:
                    _absorb(groups, a, b); merged = True
    # R3: merge when one slug is a prefix of the other
    merged = True
    while merged:
        merged = False
        keys = sorted(groups, key=len)
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                a, b = keys[i], keys[j]
                if a not in groups or b not in groups:
                    continue
                if b.startswith(a + "-"):
                    _absorb(groups, a, b); merged = True

    out = []
    for slug, g in groups.items():
        label = max(g["labels"].items(), key=lambda kv: kv[1])[0]
        ss = sorted(g["sessions"], key=lambda x: (x["first_ts"] or ""))
        out.append({
            "slug": slug,
            "label": label,
            "sessions": ss,
            "prompts": sum(s["human_prompts"] for s in ss),
            "first": min((s["first_ts"] or "9") for s in ss),
            "last":  max((s["last_ts"] or "0") for s in ss),
        })
    out.sort(key=lambda g: -g["prompts"])
    return out


def _absorb(groups, keep, drop):
    """Merge group `drop` into group `keep`."""
    k, d = groups[keep], groups.pop(drop)
    k["sessions"].extend(d["sessions"])
    k["sigs"] |= d["sigs"]
    for lbl, n in d["labels"].items():
        k["labels"][lbl] = k["labels"].get(lbl, 0) + n


def folder_path_for(project_dir):
    """A sanitised project directory name back to the folder it means.

    Claude Code names a project directory after the working directory with
    its separators flattened, so the prefix is the workspace spelled that
    way rather than one particular machine's.
    """
    if project_dir == PREFIX:
        return ROOT
    tail = project_dir[len(PREFIX) + 1:]
    root = ROOT
    for name in os.listdir(root):
        if os.path.isdir(os.path.join(root, name)):
            if name.replace(" ", "-") == tail or name == tail:
                return os.path.join(root, name)
    return None


def load_plan():
    rows = json.load(io.open(os.path.join(HERE, "inventory.json"), encoding="utf-8"))
    by = {}
    for r in rows:
        by.setdefault(r["project_dir"], []).append(r)
    plan, moved = [], {}
    for pdir in sorted(by):
        if pdir == "C--Claude-Code":
            continue                      # this meta-session, nothing to carry over
        groups = group_folder(by[pdir])
        keep = []
        for g in groups:
            target = RELOCATE.get((pdir, g["slug"]))
            if target:
                g["came_from"] = pdir
                moved.setdefault(target, []).append(g)
            else:
                keep.append(g)
        plan.append({
            "project_dir": pdir,
            "folder": folder_path_for(pdir),
            "mode": "single" if len(keep) == 1 else "multi",
            "groups": keep,
        })

    # attach relocated groups to their real folder (creating an entry if needed)
    root = ROOT
    for target, groups in moved.items():
        hit = None
        for p in plan:
            if p["folder"] and os.path.basename(p["folder"]) == target:
                hit = p
                break
        if hit:
            hit["groups"].extend(groups)
            hit["groups"].sort(key=lambda g: -g["prompts"])
            hit["mode"] = "single" if len(hit["groups"]) == 1 else "multi"
        else:
            plan.append({
                "project_dir": "relocated:" + target,
                "folder": os.path.join(root, target),
                "mode": "single" if len(groups) == 1 else "multi",
                "groups": groups,
            })
    plan = [p for p in plan if p["groups"]]
    plan.sort(key=lambda p: (p["folder"] or ""))
    return plan


if __name__ == "__main__":
    plan = load_plan()
    L = []
    for p in plan:
        L.append("%-28s  %-6s  folder=%s" % (
            p["project_dir"].replace("C--Claude-Code-", ""), p["mode"].upper(), p["folder"]))
        for g in p["groups"]:
            L.append("      %-34s slug=%-34s sessions=%-2d prompts=%-4d %s..%s" % (
                oneline(g["label"], 34), g["slug"], len(g["sessions"]),
                g["prompts"], g["first"][:10], g["last"][:10]))
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(L))
