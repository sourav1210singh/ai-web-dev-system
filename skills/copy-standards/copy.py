# -*- coding: utf-8 -*-
"""Check one piece of client-facing copy against the house rules.

    python copy.py <file-or-url> [--profile general|technical|social] [--json]

The rules in this skill were a word list and one instruction to read the text
out loud. The word list is the easy half. The harder half, and the one readers
actually judge, is whether anything is being said: a page can pass every
vocabulary rule and still be filler that scans as competent.

So this reports three kinds of thing, and is honest about which is which:

- **Certain.** An em dash, an entity-encoded dash, an exclamation mark, an
  emoji, a placeholder that was never replaced. These are defects.
- **Judged.** Filler vocabulary, heading levels that skip, paragraphs over the
  cap, bold used as emphasis everywhere. These are near enough to always wrong
  to be worth reporting.
- **Signals, with no threshold.** Sentence-length spread and how many
  sentences carry a concrete specific. Uniform cadence and sentences a reader
  could have guessed are what make text read synthetic, but there is no honest
  cut-off, so the numbers are printed and the judgement is yours.

**This is not a detector.** It does not guess who wrote the text. A person can
write something that scores badly and a model can write something clean.

For a full four-axis score with 43 rules, use clearmode, which is MIT and
stdlib-only: `github.com/eugeniughelbur/clearmode`. This deliberately does not
reimplement it. What it adds is the house rules clearmode does not carry - the
dash rule including its entity forms, and the placeholder rule - and the
ability to run against a **live URL** rather than a markdown file.
"""
import io
import json
import os
import re
import sys
import unicodedata

# The two that have been asked for on 12 separate projects, in every form they
# are stored in. Searching for the literal character finds nothing when the
# renderer wrote an entity, which is the whole difficulty.
DASH = re.compile(r"[–—]|&#x?201[34];|&#821[12];|&[mn]dash;", re.I)

# A dash inside a code span or a code block is literal text being shown, not
# punctuation being used. A document that states the dash rule has to be able
# to name `&mdash;` without failing its own check, which is how this was
# found. Code is blanked before the dash check only, so a dash in the prose
# of the same document is still caught.
#
# Indented code blocks are deliberately not handled: four spaces inside a list
# is a continuation line, not code, and blanking those would hide real prose.
# Inline spans are matched on a single line so an unclosed backtick cannot run
# away and blank the rest of the document.
FENCE = re.compile(r"(?ms)^(```|~~~).*?^\1[ \t]*$")
INLINE_CODE = re.compile(r"`+[^`\n]*`+")
HTML_CODE = re.compile(r"(?is)<(code|pre|kbd|samp)\b[^>]*>.*?</\1>")


def prose_only(s):
    """The text with code removed, for checks that judge punctuation."""
    if not s:
        return s
    return INLINE_CODE.sub(" ", FENCE.sub(" ", HTML_CODE.sub(" ", s)))

# Two tiers, because flattening them is what makes a checker get switched off.
#
# Tier 1 is a tell wherever it appears in client-facing copy. Tier 2 is a
# perfectly good word that machine-written prose reaches for far more often
# than a person does, so it is worth a look and is not automatically wrong:
# "robust" is correct about an engineering property, "crucial" is correct when
# something genuinely is, "comprehensive" is only a tell when the text is
# describing itself.
#
# Selected for client-facing web copy from the vocabulary the anti-slop work
# collects, which in turn cites the published studies rather than one author's
# taste. Sources are in the skill.
FILLER_T1 = [
    "delve", "delving", "tapestry", "a testament to", "game-changer",
    "game changer", "game-changing", "supercharge", "elevate your",
    "unlock the power", "seamless", "seamlessly", "in today's fast-paced",
    "in today's digital", "it's not just", "it is not just",
    "this is where", "at its core", "in the realm of", "when it comes to",
    "at the end of the day", "the bottom line is", "here's the thing",
    "here's the deal", "without further ado", "in a nutshell", "buckle up",
    "take it to the next level", "move the needle", "bridge the gap",
    "streamline your", "embark on", "dive in", "deep dive", "let's dive",
    "synergy", "synergies", "thought leader", "pain points", "value add",
    "cutting-edge", "state-of-the-art", "revolutionize", "revolutionise",
    "unparalleled", "holistic approach", "navigate the landscape",
    "rest assured", "it goes without saying", "needless to say",
    "empower your", "empowering businesses",
]
FILLER_T2 = [
    "leverage", "utilize", "commence", "facilitate", "encompass", "paramount",
    "groundbreaking", "transformative", "endeavour", "endeavor", "harnessing",
    "spearheading", "showcasing", "underscore", "underscores", "interplay",
    "multifaceted", "meticulous", "meticulously", "bolster", "bolstered",
    "garner", "garnered", "pivotal", "vibrant", "intricate", "unprecedented",
    "foster a", "fostering a", "robust solution", "comprehensive solution",
]
PLACEHOLDER = re.compile(
    r"\[[A-Z][A-Z_ ]{2,30}\]|\bPLACEHOLDER\b|\bTODO\b|\bTBD\b|lorem ipsum"
    r"|\bXX+\b|\byour[- ]business[- ]name\b", re.I)
HEDGE_OPENER = re.compile(
    r"(?i)^\s*(it is important to note|it should be noted|it is worth noting|"
    r"in conclusion|overall|furthermore|moreover|additionally|in summary|"
    r"as we have seen|needless to say|that being said)\b")

# clearmode's profiles, which carry real numbers rather than an impression.
PROFILES = {
    "general":   {"sentence": 25, "per_para": 4, "grade": 9,  "grade_cap": 13},
    "technical": {"sentence": 28, "per_para": 5, "grade": 11, "grade_cap": 15},
    "social":    {"sentence": 20, "per_para": 2, "grade": 8,  "grade_cap": 11},
}
BOLD_SHARE = 0.05
SEV_RANK = {"DEFECT": 0, "JUDGED": 1, "SIGNAL": 2}


def strip_html(html):
    """Visible text out of served HTML. Not the rendered DOM - see the note."""
    h = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", " ", html)
    h = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = (h.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
         .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    return re.sub(r"[ \t]+", " ", h)


# A sentence in a Markdown document does not always end at the period. The
# period can be followed by closing emphasis before the space ("...any of
# it.** The whole file"), and the next sentence can open with a list marker or
# emphasis instead of a capital ("hit.\n- **Finishing"). Neither form matched,
# so consecutive sentences merged into one. Measured against a real rules
# document, this reported a 338 word sentence where the longest was 51, and
# carried that error into the reading grade and the length spread.
#
# The separator consumes the markup rather than the pattern trying to look
# past it, because a lookbehind cannot be variable width here. What must still
# NOT split is a period inside a reference or an abbreviation, which is why a
# capital is still required: "see fig. 3 and" and "use e.g. this" stay whole.
# A capital is the right test only where there is nothing else to go on. Once a
# list marker has been consumed, a new item has definitionally begun, whatever
# character follows: "- `.claude-context/INDEX.md` lists what exists" opens on
# a backtick and a dot and is still a new sentence. The marker's own trailing
# space is what keeps "-5 degrees" from being read as one.
_CLOSE = r"[*_`\"')\]]*"
_MARK = r"(?:[-*+]|\d+\.)\s+"
_OPEN = r"[*_`\"'(\[]*"
SENT_SPLIT = re.compile(r"(?<=[.!?])" + _CLOSE + r"\s+"
                        r"(?:" + _MARK + _OPEN + r"|" + _OPEN + r"(?=[A-Z]))")

# A heading carries no terminal punctuation, so it glues itself to the
# sentence below it. The paragraph check already dropped heading lines; the
# sentence-length and reading-grade checks did not, so the two disagreed about
# the same document. One definition, used by both.
HEAD_LINE = re.compile(r"^\s*(#{1,6}\s|={3,}|-{3,}\s*$)")


def sentences(text):
    body = "\n".join(l for l in text.splitlines() if not HEAD_LINE.match(l))
    parts = SENT_SPLIT.split(body.strip())
    return [s.strip() for s in parts if len(s.strip()) > 1]


def words(s):
    return re.findall(r"[A-Za-z][A-Za-z'\-]*", s)


def syllables(w):
    w = w.lower()
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1:
        n -= 1
    return max(1, n)


def reading_grade(text):
    """Flesch-Kincaid grade level. Reported, never used as a pass or a fail."""
    ss = sentences(text)
    ws = words(text)
    if not ss or not ws:
        return None
    syl = sum(syllables(w) for w in ws)
    return round(0.39 * (len(ws) / len(ss)) + 11.8 * (syl / len(ws)) - 15.59, 1)


def has_specific(s):
    """Does this sentence carry something a reader could not have guessed?

    A proxy, and a weak one: a number, a proper noun that is not just the first
    word, or a unit. It is reported as a proportion rather than per sentence,
    because the proxy is not good enough to accuse a single sentence with.
    """
    if re.search(r"\d", s):
        return True
    ws = words(s)
    for w in ws[1:]:
        if w[:1].isupper() and w.lower() not in ("i",):
            return True
    return False


def emoji_in(text):
    out = []
    for ch in text:
        if unicodedata.category(ch) == "So" and ch not in "→←®™©":
            out.append(ch)
    return out


def check(text, html=None, profile="general"):
    p = PROFILES.get(profile, PROFILES["general"])
    f = []
    add = lambda sev, id_, title, detail="": f.append(
        {"sev": sev, "id": id_, "title": title, "detail": detail})

    # ------------------------------------------------------------ certain
    # Both sides have to be code-free, and the visible text cannot be made so
    # by blanking: by the time it reaches here the tags are gone, so there is
    # nothing left to say a span was <code>. Where the HTML is available the
    # text side is therefore re-derived from the code-free HTML rather than
    # taken as passed, which is how the caller produced it in the first place.
    h_pr = prose_only(html)
    t_pr = prose_only(strip_html(h_pr) if html else text)
    hits = DASH.findall(h_pr or t_pr) + (DASH.findall(t_pr) if html else [])
    if hits:
        kinds = sorted({("entity" if h.startswith("&") else "character")
                        for h in hits})
        add("DEFECT", "dash",
            "%d em or en dash(es) present" % len(hits),
            "Found as: " + ", ".join(kinds)
            + ". Replace with a comma, a colon, a full stop or a rewritten "
              "sentence. A spaced hyphen is its own tell.")

    bangs = text.count("!")
    if bangs:
        add("DEFECT", "exclamation", "%d exclamation mark(s)" % bangs)

    em = emoji_in(text)
    if em:
        add("DEFECT", "emoji", "%d emoji in the copy" % len(em),
            "".join(sorted(set(em))[:10]))

    ph = PLACEHOLDER.findall(text)
    if ph:
        add("DEFECT", "placeholder",
            "%d placeholder(s) still in the text" % len(ph),
            ", ".join(sorted(set(ph))[:6])
            + ". A marked placeholder is correct while drafting and is the one "
              "thing that must never ship.")

    # ------------------------------------------------------------- judged
    low = text.lower()
    t1 = sorted({w for w in FILLER_T1 if w in low})
    if t1:
        add("JUDGED", "filler", "%d filler phrase(s)" % len(t1),
            ", ".join(t1[:10]) + ". These are a tell wherever they appear.")
    t2 = sorted({w for w in FILLER_T2 if w in low})
    if t2:
        add("JUDGED", "filler-context",
            "%d word(s) machine prose over-reaches for" % len(t2),
            ", ".join(t2[:10]) + ". Each one is a real word and may be the "
            "right one here. Read them in place rather than replacing them on "
            "sight.")

    # Staccato: a run of very short sentences used for effect. One is a choice,
    # four in a row is a cadence nobody writes by accident.
    short_run, worst = 0, 0
    for s in sentences(text):
        if len(words(s)) <= 4:
            short_run += 1
            worst = max(worst, short_run)
        else:
            short_run = 0
    if worst >= 4:
        add("JUDGED", "staccato",
            "%d very short sentences in a row" % worst,
            "Punchy fragments stacked for effect. One lands; a run of them is "
            "a rhythm that reads manufactured. Join them into prose.")

    hedges = [s for s in sentences(text) if HEDGE_OPENER.match(s)]
    if hedges:
        add("JUDGED", "hedge-opener",
            "%d sentence(s) open with a filler phrase" % len(hedges),
            hedges[0][:70] + ". The sentence usually reads better without it.")

    heads = [len(h) for h in re.findall(r"(?m)^(#{1,6})\s", text)]
    heads += [int(m) for m in re.findall(r"(?i)<h([1-6])[^> ]*[^>]*>", html or "")]
    skips = [(a, b) for a, b in zip(heads, heads[1:]) if b - a > 1]
    if skips:
        add("JUDGED", "heading-skip",
            "%d heading level skip(s)" % len(skips),
            "h%d then h%d. Go one level at a time." % skips[0])

    # Headings are not sentences in a paragraph. Counting them made a four
    # line section under an h1 read as a five sentence paragraph.
    prose = "\n".join(l for l in text.splitlines() if not HEAD_LINE.match(l))
    paras = [q for q in re.split(r"\n\s*\n", prose) if q.strip()]
    longp = [q for q in paras if len(sentences(q)) > p["per_para"]]
    if longp:
        add("JUDGED", "paragraph-length",
            "%d paragraph(s) over %d sentences" % (len(longp), p["per_para"]),
            "Break at the topic shift.")

    ws_all = words(text)
    bold = re.findall(r"\*\*(.+?)\*\*", text) + re.findall(r"(?is)<(?:b|strong)>(.*?)</", html or "")
    bold_words = sum(len(words(b)) for b in bold)
    # Not below 50 words. One bold word in a ten word sentence is 10% and
    # means nothing; the rule is about a page, not a sentence.
    if len(ws_all) >= 50 and bold_words / len(ws_all) > BOLD_SHARE:
        add("JUDGED", "bold-share",
            "%.0f%% of the words are bold" % (100 * bold_words / len(ws_all)),
            "Keep it under %.0f%%. Bold everywhere emphasises nothing."
            % (100 * BOLD_SHARE))

    ss = sentences(text)
    longs = [s for s in ss if len(words(s)) > p["sentence"]]
    if longs:
        add("JUDGED", "sentence-length",
            "%d sentence(s) over %d words" % (len(longs), p["sentence"]),
            "Longest: %d words." % max(len(words(s)) for s in ss))

    # ------------------------------------------------- signals, no threshold
    lens = [len(words(s)) for s in ss] or [0]
    if len(lens) >= 5:
        mean = sum(lens) / len(lens)
        var = sum((x - mean) ** 2 for x in lens) / len(lens)
        cv = (var ** 0.5) / mean if mean else 0
        add("SIGNAL", "cadence",
            "Sentence length: %d to %d words, mean %.0f, spread %.2f"
            % (min(lens), max(lens), mean, cv),
            "Spread is the standard deviation over the mean. Prose that all "
            "runs to one length reads synthetic however good the words are. "
            "There is no honest cut-off, so judge it by reading a paragraph.")

    if ss:
        concrete = sum(1 for s in ss if has_specific(s))
        add("SIGNAL", "specifics",
            "%d of %d sentences carry a number or a name"
            % (concrete, len(ss)),
            "The real complaint about machine-written copy is not its "
            "vocabulary, it is that nothing is being said. Ask of each "
            "sentence: could a reader have guessed it? This proxy is weak, so "
            "it counts rather than accuses.")

    g = reading_grade(text)
    if g is not None:
        add("SIGNAL", "reading-grade",
            "Reading grade %.1f (target %d, cap %d for %s)"
            % (g, p["grade"], p["grade_cap"], profile))

    return sorted(f, key=lambda x: (SEV_RANK[x["sev"]], x["title"]))


def report(src, findings, profile):
    n = lambda s: sum(1 for x in findings if x["sev"] == s)
    L = ["# Copy check - %s" % src, ""]
    L.append("%d defect(s), %d judged, %d signal(s). Profile: %s."
             % (n("DEFECT"), n("JUDGED"), n("SIGNAL"), profile))
    L.append("")
    for x in findings:
        L.append("## %s - %s" % (x["sev"], x["title"]))
        if x["detail"]:
            L.append(x["detail"])
        L.append("")
    L.append("## What this is not")
    L.append("Not a detector. It does not guess who wrote the text, and it "
             "cannot: a person can write something that scores badly and a "
             "model can write something clean. It measures whether a person "
             "can read it.")
    L.append("")
    L.append("Only the served HTML was read, not the rendered page. A renderer "
             "can introduce a dash after the fact, so check the live page too.")
    L.append("")
    L.append("For a full four-axis score across 43 rules, run clearmode "
             "(MIT, stdlib only): github.com/eugeniughelbur/clearmode")
    return "\n".join(L)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    src = args[0]
    profile = "general"
    if "--profile" in sys.argv:
        i = sys.argv.index("--profile")
        if i + 1 < len(sys.argv):
            profile = sys.argv[i + 1]

    html = None
    if src.startswith(("http://", "https://")):
        import urllib.request
        req = urllib.request.Request(src, headers={"User-Agent": "copy-check"})
        html = urllib.request.urlopen(req, timeout=40).read().decode(
            "utf-8", "replace")
        text = strip_html(html)
    elif os.path.isfile(src):
        text = io.open(src, encoding="utf-8", errors="replace").read()
        if src.lower().endswith((".html", ".htm")):
            html, text = text, strip_html(text)
    else:
        print("no such file, and not a URL: %s" % src)
        return 2

    findings = check(text, html, profile)
    if "--json" in sys.argv:
        print(json.dumps({"source": src, "profile": profile,
                          "findings": findings}, indent=2, ensure_ascii=False))
    else:
        print(report(src, findings, profile))
    return 1 if any(x["sev"] == "DEFECT" for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
