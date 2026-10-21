# -*- coding: utf-8 -*-
"""Stop hook: do not let a reply claim something is done without evidence.

Reads the turn that just finished. If the final reply claims work is complete
and that same turn produced no verification artefact, the turn is blocked with
a reason naming what to go and check.

Blocks at most once per turn, so it can never loop. Never fails the session:
every error is swallowed and logged.

Off switch:  python install.py --gate off
"""
import io, json, os, re, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(r"C:\Claude-Code", ".context-system"))
LOG = os.path.join(SYS, "hook.log")
STATE = os.path.join(SYS, "gate-state.json")
CONFIG = os.path.join(SYS, "gate.json")
TAIL = 8 * 1024 * 1024

# --- a claim that work is finished -------------------------------------
CLAIM = re.compile(
    r"(?i)(?<![a-z])("
    r"done|fixed|resolved|completed?|working now|now works|it works|"
    r"is live|went live|deployed|shipped|all good|no issues|"
    r"verified|confirmed working|passing|ready to go|"
    r"ho gaya|kar diya|kardiya|ban gaya|chal raha|theek hai|thik hai|"
    r"laga diya|lag gaya|fix kar diya|sahi ho gaya|poora ho gaya"
    r")(?![a-z])")

# --- language that means the reply is already being honest -------------
HEDGE = re.compile(
    r"(?i)(could not (verify|confirm|check|test)|not (yet )?(verified|tested|"
    r"confirmed)|unverified|i have not (checked|tested|verified)|"
    r"needs? (verifying|checking|testing)|please check|cannot confirm|"
    r"verify kar(na|ke) (nahi|pending)|test nahi kiya|abhi verify nahi)")

# --- a claim that is explicitly someone else's --------------------------
SECONDHAND = re.compile(
    r"(?i)(lovable (says|reported|claims)|the (agent|tool|build) (says|reported)|"
    r"according to|it reports|reported (as )?(done|success))")

# --- tool calls that count as evidence ---------------------------------
EVIDENCE_TOOLS = {
    "Read", "WebFetch", "NotebookRead",
}
EVIDENCE_TOOL_SUBSTR = (
    "screenshot", "browser_take_screenshot", "navigate", "get_page_text",
    "read_page", "javascript_tool", "browser_snapshot", "read_console",
    "read_network", "browser_evaluate", "browser_click", "browser_fill",
)
EVIDENCE_BASH = re.compile(
    r"(?i)\b("
    r"curl|wget|rqa\.js|verify\.py|selftest\.py|check\.py|preflight\.py|"
    r"recon\.py|leakcheck\.py|gatetest\.py|install\.py --status|"
    r"npm (run )?(build|test|lint)|npx .*(build|test)|"
    r"pytest|jest|vitest|playwright|git diff|git status|git log|"
    r"md5sum|sha256sum|certutil|diff |cmp |"
    r"psql|sqlite3|supabase|wp (db|option|post) |"
    r"Invoke-WebRequest|Test-Path|Get-Content|Get-ChildItem"
    r")\b")


def log(msg):
    try:
        with io.open(LOG, "a", encoding="utf-8") as fh:
            fh.write(msg.rstrip() + "\n")
    except Exception:
        pass


def enabled():
    try:
        return bool(json.loads(io.open(CONFIG, encoding="utf-8").read()
                               ).get("enabled", True))
    except Exception:
        return True


def tail_rows(path, nbytes=TAIL):
    size = os.path.getsize(path)
    start = max(0, size - nbytes)
    with io.open(path, "rb") as fh:
        fh.seek(start)
        data = fh.read()
    if start:
        nl = data.find(b"\n")
        data = data[nl + 1:] if nl >= 0 else b""
    rows = []
    for line in data.decode("utf-8", "replace").splitlines():
        if '"user"' not in line and '"assistant"' not in line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def last_turn(rows):
    """Everything after the final human message."""
    idx = None
    for i in range(len(rows) - 1, -1, -1):
        o = rows[i]
        if o.get("type") == "user" and o.get("origin", {}).get("kind") == "human":
            idx = i
            break
    if idx is None:
        return None, [], []
    ts = rows[idx].get("timestamp") or ""
    texts, tools = [], []
    for o in rows[idx + 1:]:
        if o.get("type") != "assistant":
            continue
        for b in (o.get("message", {}).get("content") or []):
            if not isinstance(b, dict):
                continue
            if b.get("type") == "text":
                texts.append(b.get("text", ""))
            elif b.get("type") == "tool_use":
                tools.append((b.get("name") or "", b.get("input") or {}))
    return ts, texts, tools


# --- anything a human would judge with their eyes ----------------------
UI_FILE = re.compile(r"(?i)\.(tsx|jsx|ts|js|css|scss|sass|less|html?|vue|svelte|"
                     r"astro|php|twig|liquid|mdx)$")
VISUAL_CLAIM = re.compile(
    r"(?i)\b(page|site|website|hero|header|footer|nav|menu|button|section|"
    r"layout|design|responsive|mobile|desktop|tablet|looks?|ui|component|"
    r"animation|animate|scroll|hover|colou?r|font|spacing|padding|margin|"
    r"image|banner|card|grid|slider|carousel|modal|dropdown|form|"
    r"dikhta|dikh raha|layout thik|design thik)\b")
VISUAL_EVIDENCE_ACTIONS = {"screenshot", "zoom"}
VISUAL_EVIDENCE_TOOL = re.compile(r"(?i)screenshot|gif_creator")
VISUAL_EVIDENCE_BASH = re.compile(r"(?i)\brqa\.js\b|--?screenshot|playwright.*shot|"
                                  r"\bstudy\.js\b")
# opening an image file IS looking at it. Taking the screenshot and never
# reading it is the failure this tier exists for; reading one taken a moment
# ago is not.
IMAGE_FILE = re.compile(r"(?i)\.(png|jpe?g|webp|gif|bmp|avif)$")


def has_visual_evidence(tools):
    """Did anyone actually LOOK at the rendered result?

    Reading the DOM or the code is not looking. A page can pass every
    technical check and still be visibly broken, which is the whole reason
    this tier exists.
    """
    for name, inp in tools:
        if VISUAL_EVIDENCE_TOOL.search(name):
            return True, name.split("__")[-1]
        if name in ("Read", "NotebookRead") and \
                IMAGE_FILE.search(str(inp.get("file_path") or "")):
            return True, "read %s" % os.path.basename(
                str(inp.get("file_path")))
        if str(inp.get("action") or "").lower() in VISUAL_EVIDENCE_ACTIONS:
            return True, "%s(screenshot)" % name.split("__")[-1]
        if name.lower() in ("bash", "powershell"):
            if VISUAL_EVIDENCE_BASH.search(str(inp.get("command") or "")):
                return True, "rqa.js"
    return False, None


SENTENCE = re.compile(r"[^.!?\n]+[.!?\n]?")


def claim_is_visual(prose):
    """Is the CLAIM itself about something visual?

    A reply can say "the tests pass" in one sentence and mention a button
    twenty lines later without claiming anything about how the button looks.
    Requiring both in the same sentence is the difference between catching a
    visual claim and catching the word "button".
    """
    for s in SENTENCE.findall(prose):
        if CLAIM.search(s) and VISUAL_CLAIM.search(s):
            return True
    return False


def touched_ui(tools):
    for name, inp in tools:
        if name in ("Write", "Edit", "MultiEdit"):
            if UI_FILE.search(str(inp.get("file_path") or "")):
                return True
    return False


def has_evidence(tools):
    """Did this turn actually go and look at something?"""
    for name, inp in tools:
        low = name.lower()
        if name in EVIDENCE_TOOLS:
            return True, name
        if any(s in low for s in EVIDENCE_TOOL_SUBSTR):
            return True, name
        # a browser "computer" tool carries the real action in its input
        act = str(inp.get("action") or "").lower()
        if act in ("screenshot", "zoom", "scroll", "left_click", "hover",
                   "read", "javascript_exec"):
            return True, "%s(%s)" % (name.split("__")[-1], act)
        if low in ("bash", "powershell"):
            cmd = str(inp.get("command") or "")
            m = EVIDENCE_BASH.search(cmd)
            if m:
                return True, "%s(%s)" % (name, m.group(1))
    return False, None


QUOTED = re.compile(r"```.*?```|`[^`]*`|\"[^\"\n]{0,200}\"|'[^'\n]{0,200}'|"
                    r"“[^”\n]{0,200}”", re.S)


def prose_only(text):
    """The reply's own words, with quoted speech and code removed.

    A reply that writes: when you say "publish kar diya", I will re-check
    is not claiming anything is done. Neither is a code block containing the
    word. Judging those as claims blocks honest work, and a gate that blocks
    honest work is a gate someone switches off.
    """
    return QUOTED.sub(" ", text)


def changed_something(tools):
    return any(n in ("Write", "Edit", "MultiEdit", "NotebookEdit") or
               (n.lower() in ("bash", "powershell") and
                re.search(r"(?i)\b(>|>>|tee|cp |mv |rm |sed -i|git (commit|push)|"
                          r"npm (i|install)|Set-Content|Out-File)\b",
                          str(i.get('command') or '')))
               for n, i in tools)


def main():
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    if not enabled():
        return
    tpath = payload.get("transcript_path") or ""
    sid = payload.get("session_id") or ""
    cwd = payload.get("cwd") or ""
    if not tpath or not os.path.isfile(tpath):
        return

    import ctxlib as c
    from hook_stop import resolve_folder
    if not resolve_folder(cwd, c.ROOT):
        return

    ts, texts, tools = last_turn(tail_rows(tpath))
    if not ts or not texts:
        return
    final = texts[-1]

    # already blocked this exact turn: never loop
    try:
        state = json.loads(io.open(STATE, encoding="utf-8").read())
    except Exception:
        state = {}
    if state.get(sid) == ts:
        return

    prose = prose_only(final)
    if not CLAIM.search(prose):
        return
    if HEDGE.search(final):
        c.heartbeat("Gate", "claim is already hedged, allowed")
        return
    if not changed_something(tools):
        c.heartbeat("Gate", "no change made this turn, allowed")
        return
    claim = CLAIM.search(prose).group(1)
    ok, how = has_evidence(tools)

    # Anything a person judges with their eyes needs an eye. Reading the code
    # or the DOM is not looking at it.
    visual = touched_ui(tools) or claim_is_visual(prose)
    if visual:
        seen, how_seen = has_visual_evidence(tools)
        if seen:
            c.heartbeat("Gate", "looked at it: %s" % how_seen)
            return
        state[sid] = ts
        try:
            io.open(STATE, "w", encoding="utf-8").write(json.dumps(state, indent=1))
        except Exception:
            pass
        c.heartbeat("Gate", "BLOCKED: visual claim '%s', never looked at it" % claim)
        sys.stdout.write(json.dumps({"decision": "block", "reason": (
            "This reply says \"%s\" about something a person judges with their "
            "eyes, and nothing in this turn looked at it.%s\n\n"
            "Code review and a DOM read are not looking. A page can pass every "
            "technical check and still be visibly broken: text overflowing, a "
            "button cut off, sections overlapping, the wrong colour, an image "
            "that did not load.\n\n"
            "Open it and take screenshots at 390px and 1440px, then actually "
            "read them. If anything is wrong, fix it and look again before "
            "replying.\n\n"
            "  node \"C:\\\\Claude-Code\\\\.ai-system\\\\skills\\\\responsive-qa"
            "\\\\rqa.js\" <url> --out <project>\\\\.claude-context\\\\qa\n\n"
            "That screenshots six widths and reports what it measured. For a "
            "single check, the browser pane's screenshot action is enough.\n\n"
            "If the page cannot be reached from here, say so plainly and say "
            "what you would need. That answer is allowed."
            % (claim, "" if not ok else
               "  Something was checked (%s), but that is not the same as "
               "looking at the result." % how))}))
        return

    if ok:
        c.heartbeat("Gate", "evidence found: %s" % how)
        return

    secondhand = bool(SECONDHAND.search(final))
    state[sid] = ts
    try:
        io.open(STATE, "w", encoding="utf-8").write(json.dumps(state, indent=1))
    except Exception:
        pass
    c.heartbeat("Gate", "BLOCKED: claimed '%s' with no verification" % claim)

    reason = (
        "This reply says \"%s\" but nothing in this turn checked it. Files were "
        "changed and no verification artefact was produced.\n\n"
        "Go and verify it now, then reply. What counts, by the kind of claim:\n"
        "- a page works: load it and read the HTTP status, then screenshot it "
        "at 390px and 1440px\n"
        "- a form works: submit a real test and confirm the row, email or entry "
        "arrived\n"
        "- it is deployed: check the build hash changed, not that the tool said "
        "success\n"
        "- it is fixed: reproduce the failure first, then show it gone\n"
        "- content matches: diff it element by element, never a grep\n"
        "- code is correct: run the build or the tests\n\n"
        "If it genuinely cannot be checked from here, say so plainly in the "
        "reply and say what you would need. That answer is allowed and this "
        "will not block it again."
        % claim)
    if secondhand:
        reason += ("\n\nNote: this turn quotes another tool's own report. That is "
                   "a claim to verify, not evidence.")

    sys.stdout.write(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("GATE ERROR\n" + traceback.format_exc())
    sys.exit(0)
