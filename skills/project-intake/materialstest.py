# -*- coding: utf-8 -*-
"""Does the intake read what it was given, and say what is wrong with it?

Everything here is built from scratch - a real .docx zip, a real crawl csv, a
real audio file through ffmpeg - because the failures worth catching are
wiring failures, and a stub cannot have them. Reads no client file.
"""
import importlib.util, io, json, os, shutil, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def load():
    spec = importlib.util.spec_from_file_location(
        "materialsmod", os.path.join(HERE, "materials.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_docx(path, paragraphs):
    body = "".join(
        '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % p
        for p in paragraphs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/'
           'wordprocessingml/2006/main"><w:body>%s</w:body></w:document>'
           % body)
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)


def run_main(m, args):
    """main() with its output captured, so the report itself can be checked."""
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = ["materials.py"] + args
    sys.stdout = io.StringIO()
    try:
        code = m.main()
        return code, sys.stdout.getvalue()
    finally:
        sys.argv, sys.stdout = old_argv, old_out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    m = load()

    # --- timestamps, where a wrong reading raises a false alarm -----------
    ok("reads MM:SS", m.marks_of("*[00:00]* hi *[02:30]* yes") == [0, 150])
    ok("reads H:MM:SS as hours, not minutes",
       m.marks_of("at 1:05:30 we agreed") == [3930],
       m.marks_of("at 1:05:30 we agreed"))
    ok("an hour-long transcript is not reported as five minutes",
       m.marks_of("[0:00] start [1:05:30] end")[-1] > 3600)
    ok("ignores numbers that are not times",
       m.marks_of("we need 1200 units and 4500 more") == [])
    ok("formats times as a person reads them",
       m.hms(59) == "0:59" and m.hms(600) == "10:00" and m.hms(3723) == "1:02:03")

    tmp = tempfile.mkdtemp(prefix="intake_")
    try:
        # --- a real .docx, read with no library at all -------------------
        d1 = os.path.join(tmp, "Scope of Work (1).docx")
        make_docx(d1, ["Website Migration", "Estimated 56 hours across 40 tasks",
                       "", "Counted from the live XML sitemap"])
        text, how = m.docx_text(d1)
        ok("reads a .docx out of its zip", "56 hours" in text, how)
        ok("keeps the paragraphs apart", len(text.splitlines()) == 3,
           len(text.splitlines()))
        ok("drops empty paragraphs", "" not in text.splitlines())

        bad = os.path.join(tmp, "broken.docx")
        io.open(bad, "w", encoding="utf-8").write("not a zip")
        t2, how2 = m.docx_text(bad)
        ok("says so when a .docx cannot be read", t2 == "" and "could not" in how2,
           how2)

        # --- a crawl, which is judged by its columns ---------------------
        csvp = os.path.join(tmp, "crawl-export.csv")
        io.open(csvp, "w", encoding="utf-8", newline="\n").write(
            "Address,Status Code,Title 1\n"
            "https://site.example/,200,Home\n"
            "https://site.example/about,200,About\n"
            "https://site.example/about,200,About\n"
            "https://site.example/old,301,Moved\n")
        s = m.sheet_summary(csvp)
        ok("counts the rows", s["rows"] == 4, s["rows"])
        ok("counts unique URLs, not rows", len(s["urls"]) == 3, s["urls"])
        ok("counts the status codes", s["status"].get("200") == 3, s["status"])
        # Screaming Frog and Excel both write a BOM. Read as plain utf-8 the
        # first header cell is "﻿Address", and a full crawl reports no
        # URLs at all while still looking like it worked.
        bom = os.path.join(tmp, "frog-export.csv")
        io.open(bom, "w", encoding="utf-8-sig", newline="\n").write(
            "Address,Status Code\nhttps://site.example/a,200\n"
            "https://site.example/b,404\n")
        sb = m.sheet_summary(bom)
        ok("a byte-order mark does not hide the URL column",
           len(sb["urls"]) == 2, sb)

        ok("a crawl is recognised from its columns, not its text",
           m.classify(csvp, "", s) == "crawl", m.classify(csvp, "", s))
        ok("a sheet with no URL column is not called a crawl",
           m.classify(csvp, "", {"columns": ["Name", "Qty"]}) == "sheet")

        # --- the rest of the classifier ----------------------------------
        ok("a scope document is recognised", m.classify(d1, text) == "scope")
        ok("a transcript is recognised by its timestamps alone",
           m.classify(os.path.join(tmp, "x-cc81.md"),
                      "[0:00] a [1:00] b [2:00] c [3:00] d [4:00] e") ==
           "transcript")
        ok("a recording is a recording",
           m.classify(os.path.join(tmp, "call.mp4"), "") == "recording")
        ok("an image is not a document",
           m.classify(os.path.join(tmp, "logo.png"), "") == "image")

        # --- two versions of one document, the trap ----------------------
        d2 = os.path.join(tmp, "Scope of Work updated.docx")
        make_docx(d2, ["Website Migration", "Estimated 62 hours", "New: blog"])
        code, out = run_main(m, [tmp, "--out", os.path.join(tmp, "work")])
        ok("runs clean over a folder", code == 0, code)
        ok("two scope documents are reported as a conflict",
           "2 scope documents" in out, [l for l in out.splitlines()
                                        if "scope document" in l])
        ok("it does not assume the newer one is complete",
           "not automatically the" in out)
        ok("every document's text is written out for reading",
           os.path.isfile(os.path.join(tmp, "work", "text",
                                       "Scope-of-Work-updated.docx.txt")))
        ok("a document that could not be read is reported, not left blank",
           "could not be read" in out and "broken.docx" in out,
           [l for l in out.splitlines() if "broken" in l])

        empty = os.path.join(tmp, "scanned.docx")
        make_docx(empty, ["", "   "])
        code, out2 = run_main(m, [empty, "--out", os.path.join(tmp, "w5")])
        ok("a document with no text in it is called a scan",
           "produced no text" in out2, out2[-200:])

        data = json.load(io.open(os.path.join(tmp, "work", "materials.json"),
                                 encoding="utf-8"))
        kinds = sorted(f["kind"] for f in data["files"])
        ok("the inventory records what each file is",
           kinds.count("scope") == 2 and "crawl" in kinds, kinds)

        # --- a recording against a transcript that stops early -----------
        if not shutil.which("ffmpeg"):
            print("\n(ffmpeg not installed, skipping the recording checks)")
        else:
            wav = os.path.join(tmp, "call_2026-01-01.wav")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y",
                            "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
                            "-t", "600", wav], capture_output=True, timeout=300)
            ok("a test recording was built", os.path.isfile(wav))
            info = m.media_info(wav)
            ok("measures the length", 598 <= info["duration"] <= 602,
               info.get("duration"))

            tr = os.path.join(tmp, "transcript.md")
            io.open(tr, "w", encoding="utf-8", newline="\n").write(
                "**A** *[00:00]*: hello\n**B** *[02:30]*: yes\n"
                "**A** *[05:00]*: agreed\n")
            code, out = run_main(m, [wav, tr, "--out",
                                     os.path.join(tmp, "w2")])
            ok("a transcript that stops early is called short",
               "stops early" in out, [l for l in out.splitlines()
                                      if "transcript" in l.lower()][:3])
            ok("it says how much is missing", "5:00" in out and "10:00" in out)

            flat = os.path.join(tmp, "minutes.md")
            io.open(flat, "w", encoding="utf-8", newline="\n").write(
                "We discussed the migration and agreed to proceed.\n")
            code, out = run_main(m, [wav, flat, "--out",
                                     os.path.join(tmp, "w3")])
            ok("a transcript with no timestamps is called unverified",
               "unverified" in out, out[-300:])

            code, out = run_main(m, [wav, "--out", os.path.join(tmp, "w4")])
            ok("a recording with no transcript says to transcribe it",
               "--transcribe" in out)

        # --- nothing to read -------------------------------------------
        code, out = run_main(m, [os.path.join(tmp, "nope")])
        ok("a path that does not exist is reported, not ignored",
           code == 2 and "no such path" in out, out[:120])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
