# -*- coding: utf-8 -*-
"""Does the copy check catch the house defects without accusing good writing?

The dash rule is the one that matters most here: it has been asked for on 12
projects and the difficulty is that a renderer stores it as an entity, so
searching for the character finds nothing. Every form it is stored in is
tested.

The other half of the file is about restraint. Three of the measures are
signals with no threshold, and the test pins that they stay signals: a tool
that calls good prose synthetic gets switched off, and then it is not catching
the dash either.

    python copytest.py
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import copy as C  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:120] + "]") if extra else ""))


ids = lambda l: [x["id"] for x in l]
has = lambda l, i: i in ids(l)
sev = lambda l, i: next((x["sev"] for x in l if x["id"] == i), None)

# ------------------------------------------------------------ the dash
for t, want, why in [
        ("Clear pricing — no surprises.", True, "em dash character"),
        ("Clear pricing – no surprises.", True, "en dash character"),
        ("Clear pricing &mdash; no surprises.", True, "mdash entity"),
        ("Clear pricing &ndash; no surprises.", True, "ndash entity"),
        ("Clear pricing &#8212; no surprises.", True, "decimal entity"),
        ("Clear pricing &#8211; no surprises.", True, "decimal en entity"),
        ("Clear pricing &#x2014; no surprises.", True, "hex entity"),
        ("Clear pricing - no surprises.", False, "a plain hyphen is allowed"),
        ("Go to the page → then click.", False, "an arrow is not a dash"),
        ("A well-known, long-standing firm.", False, "hyphenated words"),
]:
    ok("%s: %s" % (why, "caught" if want else "not flagged"),
       has(C.check(t), "dash") == want)

ok("the dash finding says which form it was in",
   "entity" in next(x for x in C.check("a &mdash; b") if x["id"] == "dash")["detail"])
ok("a dash in the HTML but not the stripped text is still caught",
   has(C.check("a b", "<p>a &mdash; b</p>"), "dash"),
   "the renderer introduced it, which is the case the skill warns about")
ok("a dash is a defect, not a matter of taste",
   sev(C.check("a — b"), "dash") == "DEFECT")

# ------------------------------------------- a dash in code is not a dash
#
# Found by running this checker over a rules document that states the dash
# rule: naming `&mdash;` in order to forbid it was reported as using it. Code
# is a quotation of literal text, not punctuation. The guards matter more than
# the exclusions: an exclusion that also hides a real dash in the prose has
# made the check worse, not more precise.
for t, want, why in [
        ("Never write `&mdash;` in body copy.", False,
         "an entity named inside inline code"),
        ("Never write `a — b` in body copy.", False,
         "a dash character inside inline code"),
        ("Avoid it:\n\n```\nlet s = 'a — b'\n```\n\nThat is the rule.", False,
         "a dash inside a fenced code block"),
        ("Never write `&mdash;` — it is a tell.", True,
         "a real dash in the prose beside one in code is still caught"),
        ("Avoid it:\n\n```\n'a — b'\n```\n\nClear pricing — no surprises.", True,
         "a real dash after a fenced block is still caught"),
        ("Do not use the ` character — it is reserved.", True,
         "one stray backtick must not blank the rest of the line"),
        ("Clear pricing — no surprises.", True,
         "ordinary prose is unaffected"),
]:
    ok("code span: %s" % why, has(C.check(t), "dash") == want)

ok("a dash inside <code> in the served HTML is not reported",
   not has(C.check("write &mdash; here", "<p>write <code>&amp;mdash;</code> here</p>"),
           "dash"),
   "the page is documenting the entity, not using it")
ok("but a dash in the HTML prose beside one in <code> still is",
   has(C.check("a b", "<p><code>&amp;mdash;</code> is banned &mdash; always</p>"),
       "dash"),
   "the exclusion must not become a hiding place")
ok("prose_only leaves ordinary text alone",
   C.prose_only("Clear pricing — no surprises.") ==
   "Clear pricing — no surprises.")
ok("prose_only on empty or missing input returns it unchanged",
   C.prose_only("") == "" and C.prose_only(None) is None)

# -------------------------------------------------------- other certains
ok("an exclamation mark is a defect",
   sev(C.check("Book today!"), "exclamation") == "DEFECT")
ok("emoji in the copy is a defect",
   sev(C.check("Great service \U0001F680 every time."), "emoji") == "DEFECT")
ok("an arrow is not counted as emoji",
   not has(C.check("Step one → step two."), "emoji"))
ok("a registered mark is not counted as emoji",
   not has(C.check("Brandname® is ours."), "emoji"))

for t, why in [("Contact [AUTHORNAME] today.", "a bracketed placeholder"),
               ("Figures: PLACEHOLDER jobs done.", "the word PLACEHOLDER"),
               ("Price TBD for now.", "TBD"),
               ("Lorem ipsum dolor sit amet.", "lorem ipsum"),
               ("Call your-business-name on 0113.", "an unreplaced name")]:
    ok("%s is a defect" % why, sev(C.check(t), "placeholder") == "DEFECT")
ok("the placeholder finding says it must never ship",
   "must never ship" in next(x for x in C.check("[AUTHORNAME]")
                             if x["id"] == "placeholder")["detail"])
ok("an ordinary capitalised word is not a placeholder",
   not has(C.check("We serve Leeds and Bradford."), "placeholder"))

# ------------------------------------------------------------- judged
ok("tier one filler is reported",
   has(C.check("We unlock the power of seamless synergy."), "filler"))
ok("the finding names the phrases",
   "synergy" in next(x for x in C.check("We deliver synergy.")
                     if x["id"] == "filler")["detail"])
ok("plain writing is not reported as filler",
   not has(C.check("We clear blocked drains in Leeds. A visit costs 85 pounds."),
           "filler"))

# Flattening the tiers is what makes a checker get switched off. A word that is
# often the right one has to be reported differently from a phrase that never is.
ok("tier two is reported separately from tier one",
   has(C.check("We leverage a multifaceted approach."), "filler-context")
   and not has(C.check("We leverage a multifaceted approach."), "filler"))
ok("and tier two says the word may be the right one here",
   "may be the right one" in
   next(x for x in C.check("We utilize it.") if x["id"] == "filler-context")["detail"])
ok("a genuine engineering sentence is not punished",
   not any(x["id"].startswith("filler")
           for x in C.check("The retry logic is robust under packet loss, "
                            "which is crucial for the uploader.")),
   "bare 'robust' and 'crucial' are deliberately in neither tier")
ok("both tiers carry real weight rather than one giant list",
   len(C.FILLER_T1) > 30 and len(C.FILLER_T2) > 20,
   "%d and %d" % (len(C.FILLER_T1), len(C.FILLER_T2)))

ok("a run of very short sentences is reported",
   has(C.check("It works. Every time. No excuses. Just results. "
               "And that matters to the people who pay for it."), "staccato"))
ok("one short sentence is a choice, not a cadence",
   not has(C.check("It works. The engineer tests every joint before leaving "
                   "the property, and writes down what was replaced."),
           "staccato"))
ok("the staccato finding says to join them into prose",
   "Join them into prose" in
   next(x for x in C.check("It works. Every time. No excuses. Just results. Yes.")
        if x["id"] == "staccato")["detail"])

ok("a sentence opening with a filler phrase is reported",
   has(C.check("It is important to note that the price is fixed."),
       "hedge-opener"))
ok("the same sentence without the opener is clean",
   not has(C.check("The price is fixed."), "hedge-opener"))

ok("a heading level skip is reported",
   has(C.check("# One\n\ntext here\n\n### Three\n\nmore text"), "heading-skip"))
ok("going one level at a time is not reported",
   not has(C.check("# One\n\ntext\n\n## Two\n\nmore"), "heading-skip"))
ok("a heading skip in HTML is caught too",
   has(C.check("One Three", "<h1>One</h1><h3>Three</h3>"), "heading-skip"))

long_para = " ".join("Sentence number %d here." % i for i in range(1, 8))
ok("a paragraph over the cap is reported",
   has(C.check(long_para), "paragraph-length"))
ok("a heading does not count as a sentence in the paragraph below it",
   not has(C.check("# A title\n\nOne. Two. Three."), "paragraph-length"),
   "counting it made a four line section read as five sentences")
ok("the social profile has a tighter paragraph cap",
   has(C.check("One. Two. Three.", None, "social"), "paragraph-length")
   and not has(C.check("One. Two. Three.", None, "general"), "paragraph-length"))

FILLER_WORDS = " ".join(["ordinary"] * 60)
ok("bold used on most of the words is reported",
   has(C.check("**" + FILLER_WORDS + "** and a few plain words after it here."),
       "bold-share"))
ok("a little bold on a real page is not reported",
   not has(C.check("One **key** word. " + FILLER_WORDS + "."), "bold-share"))
ok("bold share is not judged on a short fragment at all",
   not has(C.check("One **key** word among many other ordinary words now."),
           "bold-share"),
   "one bold word in ten is 10% and means nothing")

ok("a sentence over the word cap is reported",
   has(C.check(" ".join(["word"] * 30) + "."), "sentence-length"))
ok("the technical profile allows longer sentences",
   not has(C.check(" ".join(["word"] * 27) + ".", None, "technical"),
           "sentence-length")
   and has(C.check(" ".join(["word"] * 27) + ".", None, "general"),
           "sentence-length"))

# ------------------------------------------------ signals stay signals
GOOD = ("We clear blocked drains across Leeds. A visit costs 85 pounds, and we "
        "say the price before starting.\n\n"
        "Last year we handled 412 jobs. The average took 90 minutes. "
        "Call 0113 496 0000 for the same day.")
g = C.check(GOOD)
ok("good plain copy produces no defects",
   not [x for x in g if x["sev"] == "DEFECT"], ids(g))
ok("and nothing judged against it either",
   not [x for x in g if x["sev"] == "JUDGED"], ids(g))
ok("cadence is reported as a signal, never as a defect",
   sev(g, "cadence") == "SIGNAL")
ok("specifics are reported as a signal, never as a defect",
   sev(g, "specifics") == "SIGNAL")
ok("reading grade is reported as a signal, never as a defect",
   sev(g, "reading-grade") == "SIGNAL")
ok("the cadence signal says there is no honest cut-off",
   "no honest cut-off" in next(x for x in g if x["id"] == "cadence")["detail"])
ok("the specifics signal says the proxy is weak",
   "proxy is weak" in next(x for x in g if x["id"] == "specifics")["detail"],
   "it counts rather than accuses")

ok("copy full of specifics scores well on the specifics count",
   "5 of 5" in next(x for x in g if x["id"] == "specifics")["title"],
   next(x for x in g if x["id"] == "specifics")["title"])
VAGUE = ("Our approach is built on trust. We believe in quality above all. "
         "Every project matters to us. We care about the outcome. Service is "
         "what we do best.")
v = C.check(VAGUE)
ok("copy that says nothing scores low on the specifics count",
   next(x for x in v if x["id"] == "specifics")["title"].startswith("0 of"),
   next(x for x in v if x["id"] == "specifics")["title"])
ok("but it is still only a signal, not a defect",
   not [x for x in v if x["sev"] == "DEFECT"], ids(v),)

# ------------------------------------------------------------- helpers
ok("HTML is stripped to its visible text",
   "hidden" not in C.strip_html("<p>shown</p><script>hidden</script>"))
ok("entities are decoded when stripping",
   "Bath & Body" in C.strip_html("<p>Bath &amp; Body</p>"))
ok("sentences split on terminators",
   len(C.sentences("One. Two! Three? Four.")) == 4)
ok("reading grade comes back as a number",
   isinstance(C.reading_grade("The cat sat on the mat. It was warm."), float))
ok("a sentence with a figure counts as carrying a specific",
   C.has_specific("A visit costs 85 pounds."))
ok("a sentence with a place name counts too",
   C.has_specific("We cover Leeds and Bradford."))
ok("a sentence of generalities does not",
   not C.has_specific("we believe in quality above all else"))

ok("the three profiles carry real numbers rather than an impression",
   C.PROFILES["general"]["sentence"] == 25
   and C.PROFILES["social"]["sentence"] == 20
   and C.PROFILES["technical"]["grade_cap"] == 15)

txt = C.report("x.md", C.check("a — b"), "general")
ok("the report states it is not a detector", "Not a detector" in txt)
ok("it says only the served HTML was read", "not the rendered page" in txt)
ok("it points at clearmode rather than reimplementing it",
   "clearmode" in txt, "43 rules already exist, MIT and stdlib only")

# ------------------------------------------ sentences inside Markdown
#
# The splitter needed the period to sit immediately before the space and the
# next sentence to open with a capital. Markdown breaks both ends: closing
# emphasis comes between the period and the space, and a list marker comes
# before the capital. Consecutive sentences merged into one, and the error
# travelled into the reading grade and the length spread as well. Every case
# marked "was merged" below failed before the fix; the rest guard it from
# being made permissive instead of precise.
for text, want, why in [
        ("Read the whole thing.** The whole file matters.", 2,
         "was merged: closing bold before the space"),
        ("See the note.) The next point follows.", 2,
         "was merged: closing bracket before the space"),
        ("Not a search hit.\n- Finishing is not the goal.", 2,
         "was merged: a list marker opens the next sentence"),
        ("Not a search hit.\n- **Finishing** is not the goal.", 2,
         "was merged: a list marker and bold open it"),
        ("First thing here. 2. Second thing here.", 2,
         "a numbered list item opens a sentence"),
        ("One point here. Another point here.", 2,
         "plain prose still splits"),
        ("See fig. 3 and the table below.", 1,
         "a figure reference must still not split"),
        ("Use e.g. this form when writing.", 1,
         "a lowercase abbreviation must still not split"),
        ("Version 1. 5 was never shipped.", 1,
         "a bare number must not open a sentence"),
        ("survives a switch.\n- `.claude-context/INDEX.md` lists it.", 2,
         "was merged: a list item opening on code and a dot"),
        ("It fell to minus five.\n-5 degrees was the low.", 1,
         "a negative number is not a list marker"),
]:
    got = len(C.sentences(text))
    ok("markdown: %s" % why, got == want, "got %d, want %d" % (got, want))

# Counting the parts is not enough here. The old splitter also returned two
# parts for a numbered list, but cut in the wrong place and left the marker
# stuck to the sentence before it. A count-only assertion hid that, which is
# the shape of a test that tolerates its own bug.
num = C.sentences("First thing here. 2. Second thing here.")
ok("the list marker is not left stuck to the previous sentence",
   num[0] == "First thing here." and num[-1] == "Second thing here.", num)

one = C.sentences("## Scope\n\nChange only what was asked.")
ok("a heading does not glue itself to the sentence below it",
   len(one) == 1, one)
ok("the heading rule has one definition, shared with the paragraph check",
   bool(C.HEAD_LINE.match("## Scope")) and bool(C.HEAD_LINE.match("---"))
   and not C.HEAD_LINE.match("- a list item"),
   "a one-dash list item is not a horizontal rule")

# The regression in the shape it was found: a rules document written as
# Markdown bullets. It reported a 338 word sentence where the longest was 51,
# so the figure is checked against this document rather than a constant.
doc = "\n".join([
    "# How work is done",
    "",
    "- **Read the whole thing before changing it.** The whole file, not the"
    " first screen.",
    "- **Finishing is not the goal.** Being right is. There is no credit for"
    " an early answer.",
    "",
    "## Proof",
    "",
    "- **Verify more than one way.** Two angles, not the same check twice.",
])
ss = C.sentences(doc)
longest = max(len(C.words(s)) for s in ss)
ok("a markdown rules document splits into its real sentences",
   len(ss) >= 6, "%d sentences" % len(ss))
ok("the longest sentence is the document's, not the whole bullet list",
   longest <= 12, "longest %d words" % longest)
ok("headings are not counted as very short sentences",
   not has(C.check(doc), "staccato"), ids(C.check(doc)))
ok("the reading grade is computed on real sentences",
   C.reading_grade(doc) is not None and C.reading_grade(doc) < 20,
   C.reading_grade(doc))

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
