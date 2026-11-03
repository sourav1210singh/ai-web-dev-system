# -*- coding: utf-8 -*-
"""Turn anything into pictures, so it can be looked at instead of parsed.

    python render.py <file-or-url...> [--out DIR] [--every 90] [--pages 12]

A PDF becomes page images. A .docx, .xlsx or .pptx gives up the pictures
buried in it, which text extraction drops without a word. A recording becomes
frames across the whole of it. A web page becomes a screenshot at phone and
desktop width. A photograph too large to open comes back scaled.

It renders and it lists. It describes nothing, because the point is that a
person - or Claude - then opens every file it produced and looks.

Needs poppler for PDFs, ffmpeg for recordings and images, node with
playwright for pages. It says which of those is missing rather than skipping
the file quietly.
"""
import io, json, os, re, shutil, subprocess, sys, zipfile

PDF_EXT = (".pdf",)
OFFICE_EXT = (".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".pptm")
MEDIA_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".m4a", ".mp3",
             ".wav")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff")
PAGE_EXT = (".html", ".htm")

SHOT_JS = """
const { chromium } = require('playwright');
(async () => {
  const [target, outDir] = process.argv.slice(2);
  const b = await chromium.launch();
  for (const [name, w, h] of [['desktop', 1440, 900], ['phone', 390, 844]]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    try {
      await p.goto(target, { waitUntil: 'networkidle', timeout: 45000 });
    } catch (e) {
      await p.goto(target, { waitUntil: 'domcontentloaded', timeout: 45000 });
    }
    await p.waitForTimeout(1200);
    // Back to the top first. A page probed by anything else is left at the
    // footer, and a footer is no use as a picture of the page.
    await p.evaluate(() => window.scrollTo(0, 0));
    await p.waitForTimeout(400);
    await p.screenshot({ path: outDir + '/shot_' + name + '_top.png' });
    await p.screenshot({ path: outDir + '/shot_' + name + '_full.png',
                         fullPage: true });
    await p.close();
  }
  await b.close();
})().catch(e => { console.error(String(e)); process.exit(1); });
"""


def run(cmd, timeout=900):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
    except Exception as e:
        class R:
            returncode, stdout, stderr = 1, "", str(e)
        return R()


def have(tool):
    return shutil.which(tool) is not None


def made(out_dir, prefix):
    return sorted(os.path.join(out_dir, f) for f in os.listdir(out_dir)
                  if f.startswith(prefix))


def hms(s):
    s = int(s)
    return ("%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60)) if s >= 3600 \
        else ("%d:%02d" % (s // 60, s % 60))


# --- each kind of thing ------------------------------------------------
def pdf_pages(path, out_dir, limit):
    """Every page as an image, because a table in a PDF survives nothing else.

    Extracting a PDF's text interleaves the columns of every table, which
    reads as prose and is not. The page image is the only honest view of it.
    """
    os.makedirs(out_dir, exist_ok=True)
    if not have("pdftoppm"):
        return [], "poppler is not installed, so this PDF cannot be rendered"
    cmd = ["pdftoppm", "-png", "-r", "110"]
    if limit:
        cmd += ["-f", "1", "-l", str(limit)]
    p = run(cmd + [path, os.path.join(out_dir, "page")])
    got = made(out_dir, "page")
    if not got:
        return [], "pdftoppm produced nothing: %s" % (p.stderr or "")[:160]
    return got, None


def office_media(path, out_dir):
    """The pictures inside a Word, Excel or PowerPoint file.

    A .docx is a zip, and its images sit in word/media. Pulling the text out
    of one leaves every diagram, screenshot and chart behind in silence, so a
    document can be reported as read with a quarter of it never seen.
    """
    os.makedirs(out_dir, exist_ok=True)
    try:
        zf = zipfile.ZipFile(path)
    except Exception as e:
        # Only the opening is wrapped. Catching everything reported a missing
        # output folder as "not a zip", which sends you to look at the wrong
        # file entirely.
        return [], "could not be opened as a zip: %s" % e
    keep = []
    with zf as z:
        names = [n for n in z.namelist()
                 if re.match(r"(word|xl|ppt)/media/", n)
                 and n.lower().endswith(IMAGE_EXT)]
        for i, n in enumerate(sorted(names), 1):
            dst = os.path.join(out_dir, "embedded_%02d_%s"
                               % (i, os.path.basename(n)))
            with z.open(n) as src, open(dst, "wb") as fh:
                shutil.copyfileobj(src, fh)
            keep.append(dst)
    note = None
    if not keep:
        note = "no pictures are embedded in it"
    elif not have("soffice"):
        note = ("%d embedded picture(s) recovered. LibreOffice is not "
                "installed, so the page layout itself cannot be rendered - "
                "read the extracted text for the words and these for the "
                "rest." % len(keep))
    return keep, note


def video_frames(path, out_dir, every):
    os.makedirs(out_dir, exist_ok=True)
    if not have("ffmpeg") or not have("ffprobe"):
        return [], "ffmpeg is not installed, so this recording cannot be seen"
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path], timeout=180)
    try:
        dur = float(json.loads(p.stdout)["format"]["duration"])
    except Exception:
        return [], "ffprobe could not read it"
    if dur <= 0:
        return [], "it has no duration"
    run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", path,
         "-vf", "fps=1/%d,scale=1280:-2" % every, "-q:v", "4",
         os.path.join(out_dir, "frame_%03d.jpg")], timeout=1800)
    got = made(out_dir, "frame_")
    if not got:
        return [], "no video track to take frames from (%s of audio)" % hms(dur)
    # The interval filter stops at the last whole interval, so the tail of a
    # recording is never sampled. A meeting decides things at the end.
    tail = dur - (len(got) - 1) * every
    if tail > 2:
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss",
             "%.2f" % max(0, dur - 2), "-i", path, "-frames:v", "1",
             "-vf", "scale=1280:-2", "-q:v", "4",
             os.path.join(out_dir, "frame_zz_end.jpg")], timeout=300)
        got = made(out_dir, "frame_")
    return got, "%s of recording, one frame every %ds" % (hms(dur), every)


def image_ready(path, out_dir):
    """A copy that can actually be opened, scaled down if it is enormous."""
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "image_" + os.path.basename(path))
    if not have("ffmpeg"):
        shutil.copyfile(path, dst)
        return [dst], "copied as is, ffmpeg not installed to scale it"
    p = run(["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", path],
            timeout=120)
    w = h = 0
    try:
        st = json.loads(p.stdout)["streams"][0]
        w, h = int(st["width"]), int(st["height"])
    except Exception:
        pass
    if w > 2200 or h > 2200:
        dst = os.path.splitext(dst)[0] + ".png"
        run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", path,
             "-vf", "scale='min(2000,iw)':-2", dst], timeout=300)
        if os.path.isfile(dst):
            return [dst], "%dx%d, scaled down to open" % (w, h)
    shutil.copyfile(path, dst)
    return [dst], ("%dx%d" % (w, h)) if w else None


def page_shot(target, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    if not have("node"):
        return [], "node is not installed, so pages cannot be screenshotted"
    js = os.path.join(out_dir, "_shot.js")
    io.open(js, "w", encoding="utf-8", newline="\n").write(SHOT_JS)
    p = run(["node", js, target, out_dir.replace("\\", "/")], timeout=240)
    os.remove(js)
    got = made(out_dir, "shot_")
    if not got:
        return [], "playwright could not open it: %s" % (p.stderr or "")[:200]
    return got, "phone and desktop, top of page and whole page"


def render(target, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    low = target.lower()
    if low.startswith(("http://", "https://")) or low.endswith(PAGE_EXT):
        return page_shot(target, out_dir)
    if low.endswith(PDF_EXT):
        return pdf_pages(target, out_dir, render.pages)
    if low.endswith(OFFICE_EXT):
        return office_media(target, out_dir)
    if low.endswith(MEDIA_EXT):
        return video_frames(target, out_dir, render.every)
    if low.endswith(IMAGE_EXT):
        return image_ready(target, out_dir)
    return [], "there is no picture of a %s - read it as text" \
        % (os.path.splitext(target)[1] or "file with no extension")


render.every = 90
render.pages = 12


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    argv = sys.argv[1:]

    def flag(name, default=None):
        k = "--" + name
        return argv[argv.index(k) + 1] \
            if k in argv and argv.index(k) + 1 < len(argv) else default

    out = flag("out")
    every = flag("every", "90")
    pages = flag("pages", "12")
    render.every = max(1, int(every))
    render.pages = None if str(pages).lower() == "all" else max(1, int(pages))
    skip = {out, every, pages}
    targets = [a for a in argv if not a.startswith("--") and a not in skip]
    if not targets:
        print(__doc__)
        return 2

    first = targets[0]
    base = os.path.dirname(os.path.abspath(first)) \
        if not first.lower().startswith("http") else os.getcwd()
    root = os.path.abspath(out or os.path.join(base, "rendered"))

    print("# Rendered to be looked at\n")
    total, problems = 0, []
    for t in targets:
        name = os.path.basename(t.rstrip("/")) or t
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name)[:60]
        sub = os.path.join(root, safe)
        if os.path.isdir(sub):
            shutil.rmtree(sub, ignore_errors=True)
        files, note = render(t, sub)
        print("## %s\n" % name)
        if note:
            print("%s\n" % note)
        if not files:
            problems.append((name, note or "nothing was produced"))
            print("**Nothing to look at.**\n")
            continue
        total += len(files)
        for f in files:
            print("- %s" % os.path.abspath(f))
        print("")

    if problems:
        print("## Could not be rendered\n")
        for n, why in problems:
            print("- **%s** - %s" % (n, why))
        print("")

    if total:
        print("---\n")
        print("**Open all %d of these now, with the Read tool, before saying "
              "anything about what they contain.** Not a sample of them. The "
              "whole point is that the text already extracted is not what is "
              "in the file: a table reads as prose, a diagram does not appear "
              "at all, and a screen share is never spoken out loud." % total)
    return 0 if total else 1


if __name__ == "__main__":
    sys.exit(main())
