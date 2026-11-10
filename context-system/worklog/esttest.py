# -*- coding: utf-8 -*-
"""Does the estimate comparison refuse the three things it must refuse?

    python esttest.py

The cases that matter most are the refusals, because each one is a wrong number
this would otherwise state confidently: picking a table out of a scope document
on its own, comparing against work nobody approved, turning three projects into
a multiplier, and - worst of the four - reporting a label typo as having come in
under.

The fixture .docx is built here as a real zip so the table reader is exercised
rather than stubbed, and it reproduces the shape of the first real document:
a summary whose line items do not add up to one of its own figures.
"""
import io
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import estimate as E  # noqa: E402

RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%s %s%s" % ("PASS " if cond else "FAIL ", name,
                       ("  [" + str(extra)[:120] + "]") if extra else ""))


# ------------------------------------------------------------ a real .docx

NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def cell(text):
    return ("<w:tc><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:tc>"
            % text.replace("&", "&amp;").replace("<", "&lt;"))


def table(rows):
    trs = "".join("<w:tr>%s</w:tr>" % "".join(cell(c) for c in r) for r in rows)
    return "<w:tbl>%s</w:tbl>" % trs


def make_docx(path, tables):
    body = "".join(table(t) for t in tables)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document %s><w:body>%s</w:body></w:document>' % (NS, body))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0"?><Types xmlns="http://schemas.openxml'
                   'formats.org/package/2006/content-types"/>')
        z.writestr("word/document.xml", doc)


tmp = tempfile.mkdtemp(prefix="esttest-")
try:
    # Deliberately the real shape: the summary bills 35 for a workstream whose
    # detail adds to 25, one workstream reconciles, one has no detail at all.
    doc = os.path.join(tmp, "scope.docx")
    make_docx(doc, [
        [["Workstream", "Hours", "Cost"],
         ["Technical scope", "35 hrs", "$750"],
         ["Landing pages (optional add-on)", "6 hrs", "$180"],
         ["Blog content", "8 hrs", "$240"]],
        [["Task", "Hours", "Notes"],
         ["SEO audit", "2", "before anything changes"],
         ["Redirect mapping", "5", "preserve slugs"],
         ["Payment integration - build", "8", "the biggest item"],
         ["Payment integration - testing", "2", "real transactions"],
         ["Scheduling embed", "2", ""],
         ["Analytics setup", "6", ""]],
        [["Task", "Hours", "Notes"],
         ["Page one", "1.5", "research + write"],
         ["Page two", "1.5", ""],
         ["Page three", "1.5", ""],
         ["Page four", "1.5", ""]],
    ])

    tables = E.hours_tables(E.docx_tables(doc))
    ok("every hours table is found", len(tables) == 3, len(tables))
    ok("a summary table's hours parse past the unit",
       tables[0]["total"] == 49, tables[0]["total"])
    ok("a detail table totals its own rows", tables[1]["total"] == 25,
       tables[1]["total"])
    ok("fractional hours survive", tables[2]["total"] == 6, tables[2]["total"])
    ok("the cost column is picked up",
       tables[0]["items"][0]["cost"] == "$750")
    ok("items start undecided, never approved by default",
       all(i["approved"] is None for t in tables for i in t["items"]))
    ok("a table with no hours column is ignored",
       len(E.hours_tables([[["Name", "Note"], ["a", "b"]]])) == 0)

    rec = E.reconcile(tables)
    joined = " | ".join(rec)
    ok("the detail table that reconciles is paired with its summary line",
       any("accounts for" in l and "Landing pages" in l for l in rec), joined[:150])
    ok("the real discrepancy is reported as 10 hours, not 18",
       any("gap of 10 hour" in l for l in rec),
       [l for l in rec if "gap of" in l])
    ok("a workstream with no detail table is named as such",
       any("Blog content" in l and "no detail table" in l for l in rec))
    ok("the line that the gap is about is not also called detail-less",
       not any("Technical scope" in l and "no detail table" in l for l in rec),
       "saying both contradicts itself")
    ok("two unrelated tables are not forced into a pairing",
       "separate quotes" in " ".join(E.reconcile([
           {"head": [], "items": [{"task": "a", "hours": 3}], "total": 3},
           {"head": [], "items": [{"task": "b", "hours": 7}], "total": 7}])))
    ok("a single table needs no reconciling", E.reconcile(tables[:1]) == [])

    # ------------------------------------------------- record and approve
    proj = os.path.join(tmp, "Demo Client")
    os.makedirs(proj)
    E.ROOT = tmp

    rc = E.cmd_record(["Demo Client"], {"from": doc, "dated": "2026-07-22"})
    ok("record refuses to guess which table is the estimate", rc == 2)
    rc = E.cmd_record(["Demo Client"], {"from": doc, "table": "1"})
    ok("record refuses an estimate with no date", rc == 2)
    rc = E.cmd_record(["Demo Client"], {"dated": "2026-07-22"})
    ok("record needs either a document or an explicit figure", rc == 2)

    rc = E.cmd_record(["Demo Client"], {"from": doc, "table": "1",
                                        "dated": "2026-07-22", "cost": "$750"})
    saved = E.load("Demo Client")
    ok("a recorded estimate lands in the project", rc == 0 and saved)
    ok("it keeps the line items", len(saved["items"]) == 6, len(saved["items"]))
    ok("it records which table was chosen", saved.get("from_table") == 1)
    ok("it names the document it came from", "scope.docx" in saved["source"])
    ok("it warns that the other tables disagree",
       any("Other tables" in n for n in saved["notes"]))
    ok("nothing is approved on the way in",
       all(i["approved"] is None for i in saved["items"]),
       "an estimate is not an agreement")

    res, why = E.compare_one(saved, "2026-07-01", "2026-11-10")
    ok("compare refuses while any item is undecided", res is None and "undecided" in why)

    E.cmd_approve(["Demo Client"], {"item": "redirect"})
    half = E.load("Demo Client")
    ok("approving by text matches one item",
       sum(1 for i in half["items"] if i["approved"] is True) == 1)
    res, why = E.compare_one(half, "2026-07-01", "2026-11-10")
    ok("one approved item is still not enough while others are undecided",
       res is None and "undecided" in why)

    rc = E.cmd_approve(["Demo Client"], {"item": "nothing like this"})
    ok("approving something that matches nothing is an error, not a no-op", rc == 2)

    E.cmd_approve(["Demo Client"], {"all": True})
    E.cmd_approve(["Demo Client"], {"drop": "Scheduling"})
    full = E.load("Demo Client")
    ok("dropping an item takes it out of the quoted total",
       sum(i["hours"] for i in full["items"] if i["approved"] is True) == 23,
       sum(i["hours"] for i in full["items"] if i["approved"] is True))

    # -------------------------------------------- the label failure mode
    bad = dict(full)
    bad["label"] = "A Project That Does Not Exist At All"
    real = {}

    def fake_measure(start, end):
        return ({"Demo Client": {"sec": 30 * 3600, "prompts": 10,
                                 "days": set(), "bursts": 3},
                 "Something Else": {"sec": 3600, "prompts": 1,
                                    "days": set(), "bursts": 1}}, 100, 50)

    real["m"] = E.timespent.measure
    E.timespent.measure = fake_measure
    try:
        res, why = E.compare_one(bad, "2026-07-01", "2026-11-10")
        ok("a label matching no measured work is refused, not reported as 0",
           res is None and "100% under" in why,
           "otherwise every typo reads as a triumph")
        ok("the refusal lists the labels that do exist",
           "Demo Client" in why and "Something Else" in why)

        good = dict(full)
        good["label"] = "Demo Client"
        res, why = E.compare_one(good, "2026-07-01", "2026-11-10")
        ok("a real comparison comes out", res and res["actual"] == 30.0, res)
        ok("the ratio is actual over quoted",
           res and res["ratio"] == round(30.0 / 23, 2), res and res["ratio"])
        ok("only approved items are counted as quoted",
           res and res["estimated"] == 23, res and res["estimated"])

        # ------------------------------------------- calibration refusal
        buf = io.StringIO()
        keep, sys.stdout = sys.stdout, buf
        try:
            E.cmd_calibrate([], {})
        finally:
            sys.stdout = keep
        out = buf.getvalue()
        ok("calibrate shows the one project it has", "Demo Client" in out)
        ok("calibrate refuses to give a multiplier from too few projects",
           "not enough" in out.lower() or "anecdote" in out.lower(),
           [l for l in out.splitlines() if "anecdote" in l])
        ok("it says how many it would need", str(E.MIN_PROJECTS) in out)
        ok("no median is printed on thin data", "median" not in out.lower())
    finally:
        E.timespent.measure = real["m"]

    # ------------------------------------------------------ manual record
    proj2 = os.path.join(tmp, "Call Quote")
    os.makedirs(proj2)
    E.cmd_record(["Call Quote"], {"hours": "40", "for": "migration",
                                  "dated": "2026-11-02",
                                  "source": "agreed on the 2 Nov call"})
    man = E.load("Call Quote")
    ok("a figure agreed on a call can be recorded with no document",
       man and man["items"][0]["hours"] == 40.0)
    ok("it records where the figure came from",
       "2 Nov call" in man["source"])
    ok("a hand-recorded item says so",
       "by hand" in man["items"][0]["note"])

    # ------------------------------------------------------- the caveat
    ok("the method's limits travel with the number",
       "floor for hands-on time" in E.CAVEAT and "not an invoice" in E.CAVEAT)
    ok("the caveat points the right way", "gap above" in E.CAVEAT)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

passed = sum(1 for r in RESULTS if r)
print("\n%d/%d checks passed" % (passed, len(RESULTS)))
sys.exit(0 if passed == len(RESULTS) else 1)
