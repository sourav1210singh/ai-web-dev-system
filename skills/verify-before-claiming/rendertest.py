# -*- coding: utf-8 -*-
"""Does it actually produce something that can be looked at, and say so when
it cannot?

Builds its own PDF, .docx, clip and oversized image, because the failure that
matters here is a file reported as handled when nothing was rendered.
"""
import importlib.util, io, os, shutil, subprocess, sys, tempfile, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def load():
    spec = importlib.util.spec_from_file_location(
        "rendermod", os.path.join(HERE, "render.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def make_pdf(path):
    objs = [b"<</Type/Catalog/Pages 2 0 R>>",
            b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 120]/Contents 4 0 R"
            b"/Resources<</Font<</F1 5 0 R>>>>>>",
            None,
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    stream = b"BT /F1 28 Tf 30 50 Td (LOOK AT ME) Tj ET"
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        if o is None:
            o = b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream"
        out += b"%d 0 obj" % i + o + b"endobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for off in offs:
        out += b"%010d 00000 n \n" % off
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" \
        % (len(objs) + 1, xref)
    open(path, "wb").write(bytes(out))


PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
       b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
       b"\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")


def make_docx(path, with_image):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml",
                   '<w:document><w:body><w:p><w:r><w:t>Scope</w:t></w:r>'
                   '</w:p></w:body></w:document>')
        if with_image:
            z.writestr("word/media/image1.png", PNG)
            z.writestr("word/media/image2.jpeg", PNG)


def run_main(m, args):
    old_argv, old_out = sys.argv, sys.stdout
    sys.argv = ["render.py"] + args
    sys.stdout = io.StringIO()
    try:
        return m.main(), sys.stdout.getvalue()
    finally:
        sys.argv, sys.stdout = old_argv, old_out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    m = load()
    tmp = tempfile.mkdtemp(prefix="look_")
    try:
        work = os.path.join(tmp, "out")

        # --- the pictures buried in an office file ----------------------
        dx = os.path.join(tmp, "Scope of Work.docx")
        make_docx(dx, with_image=True)
        files, note = m.office_media(dx, work)
        ok("recovers the pictures text extraction drops", len(files) == 2,
           [os.path.basename(f) for f in files])
        ok("what it recovers is a real image",
           open(files[0], "rb").read(8) == b"\x89PNG\r\n\x1a\n")
        ok("says the layout itself still cannot be rendered",
           note and "layout" in note, note)

        plain = os.path.join(tmp, "plain.docx")
        make_docx(plain, with_image=False)
        f2, n2 = m.office_media(plain, os.path.join(work, "p"))
        ok("a document with no pictures says so", f2 == [] and "no pictures"
           in (n2 or ""), n2)

        broken = os.path.join(tmp, "broken.docx")
        io.open(broken, "w", encoding="utf-8").write("not a zip")
        f3, n3 = m.office_media(broken, os.path.join(work, "b"))
        ok("a file that is not really a .docx is reported",
           f3 == [] and "zip" in (n3 or ""), n3)

        # --- a PDF, where the text is the lie ---------------------------
        if not shutil.which("pdftoppm"):
            print("\n(poppler not installed, skipping the PDF checks)")
        else:
            pdf = os.path.join(tmp, "scope.pdf")
            make_pdf(pdf)
            d = os.path.join(work, "pdf")
            os.makedirs(d, exist_ok=True)
            m.render.pages = 12
            files, note = m.pdf_pages(pdf, d, 12)
            ok("renders a PDF page to an image", len(files) >= 1, files)
            ok("the page image is a real PNG",
               files and open(files[0], "rb").read(8) == b"\x89PNG\r\n\x1a\n")

        # --- a recording ------------------------------------------------
        if not shutil.which("ffmpeg"):
            print("\n(ffmpeg not installed, skipping the recording checks)")
        else:
            clip = os.path.join(tmp, "call.mp4")
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
                 "-i", "testsrc=size=320x180:rate=10:duration=25",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", clip],
                capture_output=True, timeout=300)
            d = os.path.join(work, "vid")
            os.makedirs(d, exist_ok=True)
            files, note = m.video_frames(clip, d, 10)
            ok("takes frames across a recording", len(files) >= 3, len(files))
            ok("the last frame reaches the end",
               any("zz_end" in f for f in files),
               [os.path.basename(f) for f in files])

            wav = os.path.join(tmp, "audio.wav")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f",
                            "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-t",
                            "5", wav], capture_output=True, timeout=120)
            d2 = os.path.join(work, "aud")
            os.makedirs(d2, exist_ok=True)
            f4, n4 = m.video_frames(wav, d2, 10)
            ok("audio with no video says so instead of going quiet",
               f4 == [] and "no video track" in (n4 or ""), n4)

            # --- an image too big to open ------------------------------
            big = os.path.join(tmp, "huge.png")
            subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f",
                            "lavfi", "-i", "color=c=red:s=3000x3000:d=1",
                            "-frames:v", "1", big], capture_output=True,
                           timeout=120)
            d3 = os.path.join(work, "img")
            os.makedirs(d3, exist_ok=True)
            f5, n5 = m.image_ready(big, d3)
            ok("an enormous image comes back scaled down",
               f5 and "scaled" in (n5 or ""), n5)

        # --- things with no picture ------------------------------------
        txt = os.path.join(tmp, "notes.txt")
        io.open(txt, "w", encoding="utf-8").write("hello")
        f6, n6 = m.render(txt, os.path.join(work, "t"))
        ok("a text file is not pretended to have a picture",
           f6 == [] and "read it as text" in (n6 or ""), n6)

        # --- end to end -------------------------------------------------
        code, out = run_main(m, [dx, txt, "--out", os.path.join(tmp, "r2")])
        ok("runs over a mixed set", code == 0, code)
        ok("lists every file by absolute path",
           out.count(os.path.join(tmp, "r2")) >= 2,
           [l for l in out.splitlines() if "r2" in l][:2])
        ok("ends by saying to open all of them",
           "Open all" in out and "Not a sample" in out)
        ok("what it could not render is listed, not dropped",
           "Could not be rendered" in out and "notes.txt" in out)

        code, out = run_main(m, [txt, "--out", os.path.join(tmp, "r3")])
        ok("nothing rendered is a non-zero exit", code == 1, code)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
