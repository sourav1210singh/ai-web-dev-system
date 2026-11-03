# -*- coding: utf-8 -*-
"""Inventory everything handed over at the start of a project, and read it.

    python materials.py <folder-or-files...> [--site URL] [--out DIR]

Given a folder, or a list of paths, it works out what each file is, pulls the
text out of every document so none of it can be skipped, measures every
recording, and reconciles the counts that matter on a migration.

It reads and reports. It decides nothing: the skill beside this says what to
do with what comes out.

Handles: pdf (pdftotext, falling back to pypdf), docx (read straight out of
the zip, no library needed), csv and xlsx, md and txt, and any video or audio
ffprobe can open.
"""
import csv as csvmod
import io, json, os, re, subprocess, sys, zipfile
from collections import Counter

DOC_EXT = (".pdf", ".docx", ".md", ".txt", ".rtf")
SHEET_EXT = (".csv", ".tsv", ".xlsx", ".xls")
MEDIA_EXT = (".mp4", ".mov", ".mkv", ".webm", ".m4a", ".mp3", ".wav", ".avi")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")

URL_RX = re.compile(r"https?://[^\s,\"'<>)\]]+")
STAMP_RX = re.compile(r"(?<!\d)\d{1,2}:[0-5]\d(?!\d)")


def run(cmd, timeout=600):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except Exception:
        return None


def which(tool):
    from shutil import which as w
    return w(tool)


# --- text out of each kind of document ---------------------------------
def pdf_text(path):
    if which("pdftotext"):
        out = path + ".__tmp.txt"
        p = run(["pdftotext", "-layout", path, out])
        if p is not None and os.path.isfile(out):
            t = io.open(out, encoding="utf-8-sig", errors="replace").read()
            os.remove(out)
            if t.strip():
                return t, "pdftotext"
    try:
        from pypdf import PdfReader
        r = PdfReader(path)
        return "\n".join((pg.extract_text() or "") for pg in r.pages), "pypdf"
    except Exception as e:
        return "", "could not read (%s)" % e


def docx_text(path):
    """A .docx is a zip; the body is word/document.xml. No library needed."""
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as e:
        return "", "could not read (%s)" % e
    paras = []
    for blk in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
        txt = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", blk, re.S))
        txt = re.sub(r"<[^>]+>", "", txt).strip()
        if txt:
            paras.append(txt)
    return "\n".join(paras), "docx zip"


def sheet_summary(path):
    """Columns, row count and any URL column, which is the point of a crawl."""
    rows, header = [], []
    if path.lower().endswith((".csv", ".tsv")):
        delim = "\t" if path.lower().endswith(".tsv") else ","
        try:
            # utf-8-sig, because Screaming Frog and Excel both write a BOM and
            # it lands inside the first header cell. Read as plain utf-8 the
            # "Address" column is named "﻿Address", no URL column is
            # found, a 152 row crawl reports 0 URLs, and the comparison
            # against the sitemap below is skipped without a word.
            with io.open(path, encoding="utf-8-sig", errors="replace",
                         newline="") as fh:
                rd = csvmod.reader(fh, delimiter=delim)
                for i, r in enumerate(rd):
                    if i == 0:
                        header = r
                    else:
                        rows.append(r)
        except Exception as e:
            return {"error": str(e)}
    else:
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            ws = wb[wb.sheetnames[0]]
            for i, r in enumerate(ws.iter_rows(values_only=True)):
                vals = ["" if v is None else str(v) for v in r]
                if i == 0:
                    header = vals
                else:
                    rows.append(vals)
        except Exception as e:
            return {"error": str(e)}

    urls, status = [], Counter()
    low = [h.strip().lower() for h in header]
    u_i = next((i for i, h in enumerate(low)
                if h in ("address", "url", "page", "loc")), None)
    s_i = next((i for i, h in enumerate(low)
                if "status code" in h or h == "status"), None)
    for r in rows:
        if u_i is not None and u_i < len(r) and r[u_i].startswith("http"):
            urls.append(r[u_i].strip())
        if s_i is not None and s_i < len(r) and r[s_i]:
            status[r[s_i].strip()] += 1
    return {"columns": header[:20], "rows": len(rows),
            "urls": sorted(set(urls)), "status": dict(status.most_common(8))}


def media_info(path):
    if not which("ffprobe"):
        return {"error": "ffprobe not installed"}
    p = run(["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-show_entries", "stream=codec_type",
             "-of", "json", path], timeout=180)
    try:
        d = json.loads(p.stdout)
    except Exception:
        return {"error": "ffprobe could not read it"}
    dur = float((d.get("format") or {}).get("duration") or 0)
    kinds = [s.get("codec_type") for s in (d.get("streams") or [])]
    return {"duration": dur, "has_audio": "audio" in kinds,
            "has_video": "video" in kinds}


def marks_of(text):
    """Every timestamp in a transcript, in seconds, in order.

    H:MM:SS has to be read as such. Reading only MM:SS turns 1:05:30 into
    5:30, so an hour-long meeting's transcript looks like it stopped after
    five minutes and the report raises a false alarm.
    """
    out = []
    for h, m, s in re.findall(
            r"(?<!\d)(\d{1,2}):([0-5]\d)(?::([0-5]\d))?(?!\d)", text or ""):
        out.append(int(h) * 3600 + int(m) * 60 + int(s) if s
                   else int(h) * 60 + int(m))
    return sorted(out)


def hms(s):
    s = int(s)
    return ("%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)) if s >= 3600 \
        else ("%d:%02d" % (s // 60, s % 60))


def classify(path, text, sheet=None):
    """What this file is for, from its name and what is in it.

    A spreadsheet is judged by its columns, never by `text`: nothing extracts
    text from a sheet, so reading one that way classified the client's crawl
    as an ordinary sheet and the whole URL reconciliation below was skipped
    without a word.
    """
    n = os.path.basename(path).lower()
    low = path.lower()
    if low.endswith(MEDIA_EXT):
        return "recording"
    if low.endswith(SHEET_EXT):
        cols = " ".join(sheet.get("columns") or []).lower() if sheet else ""
        return "crawl" if ("address" in cols or "status code" in cols
                           or "url" in cols) else "sheet"
    if low.endswith(IMAGE_EXT):
        return "image"
    if any(k in n for k in ("scope", "sow", "proposal", "contract", "quote")):
        return "scope"
    # A transcript is recognisable by its timestamps even when the file is
    # named after a meeting id rather than "transcript".
    if any(k in n for k in ("transcript", "minutes")) or \
            len(STAMP_RX.findall(text or "")) >= 5:
        return "transcript"
    return "document"


def live_sitemap(site):
    """How many URLs the site says it has today."""
    if not site:
        return None
    base = site.rstrip("/")
    url = base if base.endswith(".xml") else base + "/sitemap.xml"
    p = run(["curl", "-s", "--compressed", "--max-time", "40", url], timeout=90)
    if p is None or not p.stdout:
        return {"url": url, "error": "could not be fetched"}
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", p.stdout)
    children = [l for l in locs if l.endswith(".xml")]
    return {"url": url, "urls": len(locs), "child_sitemaps": children[:20],
            "is_index": bool(children) and len(children) == len(locs)}


def main():
    if hasattr(sys.stdout, "reconfigure"):     # not a StringIO under test
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    def flag(name, default=None):
        return argv[argv.index("--" + name) + 1] \
            if "--" + name in argv and argv.index("--" + name) + 1 < len(argv) \
            else default
    site = flag("site")
    targets = []
    skip = {site, flag("out")}
    for a in argv:
        if a.startswith("--") or a in skip:
            continue
        targets.append(a)
    if not targets:
        print(__doc__)
        return 2

    paths = []
    for t in targets:
        if os.path.isdir(t):
            for f in sorted(os.listdir(t)):
                fp = os.path.join(t, f)
                if os.path.isfile(fp) and not f.startswith("."):
                    paths.append(fp)
        elif os.path.isfile(t):
            paths.append(t)
        else:
            print("no such path: %s" % t)
    if not paths:
        print("nothing to read")
        return 2

    base = os.path.dirname(os.path.abspath(paths[0]))
    out_dir = os.path.abspath(flag("out") or os.path.join(base, "materials"))
    tdir = os.path.join(out_dir, "text")
    os.makedirs(tdir, exist_ok=True)

    print("# Project materials\n")
    print("reading %d file(s)\nworkspace: %s\n" % (len(paths), out_dir))

    found = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        rec = {"path": os.path.abspath(p), "name": os.path.basename(p),
               "mb": round(os.path.getsize(p) / 1048576.0, 2), "ext": ext}
        text = ""
        if ext == ".pdf":
            text, how = pdf_text(p)
            rec["read_with"] = how
        elif ext == ".docx":
            text, how = docx_text(p)
            rec["read_with"] = how
        elif ext in (".md", ".txt", ".rtf"):
            text = io.open(p, encoding="utf-8-sig", errors="replace").read()
            rec["read_with"] = "plain"
        elif ext in SHEET_EXT:
            rec["sheet"] = sheet_summary(p)
        elif ext in MEDIA_EXT:
            rec["media"] = media_info(p)

        if text:
            rec["words"] = len(text.split())
            safe = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(p))
            tp = os.path.join(tdir, safe + ".txt")
            io.open(tp, "w", encoding="utf-8", newline="\n").write(text)
            rec["text_file"] = tp
            rec["urls"] = sorted(set(URL_RX.findall(text)))[:30]
        rec["kind"] = classify(p, text, rec.get("sheet"))
        found.append(rec)

    # ---- the inventory -------------------------------------------------
    print("| file | kind | size | read |")
    print("|---|---|---|---|")
    for r in found:
        detail = ""
        if r.get("words"):
            detail = "%d words" % r["words"]
        elif r.get("sheet", {}).get("rows") is not None:
            detail = "%d rows" % r["sheet"]["rows"]
        elif r.get("media", {}).get("duration"):
            detail = hms(r["media"]["duration"])
        print("| `%s` | %s | %.1f MB | %s |"
              % (r["name"], r["kind"], r["mb"], detail or "-"))
    print("")

    # ---- what needs attention ------------------------------------------
    notes = []

    # A document that was handed over and not read is the whole failure this
    # exists to prevent, so it is never left as a dash in the table.
    for r in found:
        if "could not read" in (r.get("read_with") or ""):
            notes.append("**`%s` could not be read** (%s). Nothing in it has "
                         "been taken into account. Convert it or open it by "
                         "hand before going further."
                         % (r["name"], r["read_with"]))
        elif r.get("read_with") and not r.get("words"):
            notes.append("**`%s` produced no text.** It is almost certainly a "
                         "scan or an export of images, so the words in it are "
                         "invisible to every check below. Read it as images, "
                         "or OCR it." % r["name"])

    scopes = [r for r in found if r["kind"] == "scope"]
    if len(scopes) > 1:
        notes.append(
            "**%d scope documents.** %s. They are not interchangeable: read "
            "both and diff them. The newer one is not automatically the "
            "complete one, and a line dropped between versions is exactly "
            "what gets argued about later."
            % (len(scopes), ", ".join("`%s` (%s words)"
                                      % (r["name"], r.get("words", 0))
                                      for r in scopes)))

    recs = [r for r in found if r["kind"] == "recording"]
    trans = [r for r in found if r["kind"] == "transcript"]
    for r in recs:
        d = (r.get("media") or {}).get("duration") or 0
        if not trans:
            notes.append("`%s` runs %s and no transcript came with it. Run "
                         "meeting-intake with --transcribe." % (r["name"], hms(d)))
            continue
        for t in trans:
            body = io.open(t["text_file"], encoding="utf-8",
                           errors="replace").read() if t.get("text_file") else ""
            marks = marks_of(body)
            if not marks:
                notes.append(
                    "`%s` carries no timestamps, so there is no way to tell "
                    "which part of `%s` it covers. Treat it as unverified."
                    % (t["name"], r["name"]))
            elif d and d - marks[-1] > 180:
                notes.append(
                    "**The transcript stops early.** `%s` reaches %s but "
                    "`%s` runs to %s, so the last %s is missing - and that is "
                    "where meetings decide things."
                    % (t["name"], hms(marks[-1]), r["name"], hms(d),
                       hms(d - marks[-1])))
            elif d:
                notes.append("`%s` reaches %s of `%s` (%s). Covered."
                             % (t["name"], hms(marks[-1]), r["name"], hms(d)))

    crawls = [r for r in found if r["kind"] == "crawl"]
    sm = live_sitemap(site) if site else None
    if crawls or sm:
        print("## URL counts\n")
        if sm and sm.get("urls") is not None:
            if sm.get("is_index"):
                print("- live sitemap `%s` is an index pointing at %d child "
                      "sitemaps, so the real page count is the sum of those, "
                      "not %d" % (sm["url"], len(sm["child_sitemaps"]),
                                  sm["urls"]))
            else:
                print("- live sitemap `%s`: **%d URLs**" % (sm["url"], sm["urls"]))
        elif sm:
            print("- live sitemap `%s`: %s" % (sm["url"], sm.get("error")))
        for c in crawls:
            s = c["sheet"]
            print("- crawl `%s`: **%d unique URLs** over %d rows%s"
                  % (c["name"], len(s.get("urls") or []), s.get("rows", 0),
                     (", status " + ", ".join("%s x%d" % (k, v)
                      for k, v in (s.get("status") or {}).items()))
                     if s.get("status") else ""))
        if sm and sm.get("urls") and crawls and not sm.get("is_index"):
            cu = len(crawls[0]["sheet"].get("urls") or [])
            if cu and abs(cu - sm["urls"]) > max(3, 0.1 * sm["urls"]):
                notes.append(
                    "**The crawl and the sitemap disagree**: %d crawled "
                    "against %d in the sitemap. One of them is wrong about "
                    "what this site is, and a migration counted off the wrong "
                    "one ships with pages missing." % (cu, sm["urls"]))
        print("")

    if notes:
        print("## Read this before anything else\n")
        for n in notes:
            print("- %s" % n)
        print("")

    io.open(os.path.join(out_dir, "materials.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(
                {"site": site, "files": found, "sitemap": sm}, indent=1) + "\n")
    print("Text of every document is in %s - read all of it, not the "
          "inventory above." % tdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
