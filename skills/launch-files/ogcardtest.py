# -*- coding: utf-8 -*-
"""Does ogcard.py produce a card that actually meets the spec?

Builds its own source images, so it needs no photo and no network.
"""
import io, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
RESULTS = []

try:
    from PIL import Image
except ImportError:
    print("needs Pillow:  pip install Pillow")
    sys.exit(2)


def ok(name, cond, extra=""):
    RESULTS.append(bool(cond))
    print("%-5s %s%s" % ("PASS" if cond else "FAIL", name,
                         ("  [%s]" % extra) if extra else ""))


def run(args):
    p = subprocess.run([PY, "-X", "utf8", "-I",
                        os.path.join(HERE, "ogcard.py")] + args,
                       capture_output=True, text=True, timeout=180)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def noisy(path, w, h, bright):
    """A photo-ish image: flat colour would compress to nothing and prove
    nothing about the size budget."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(0, w, 1):
            v = (x * 7 + y * 13) % 256
            px[x, y] = (min(255, bright + v // 3), (v * 2) % 256, v)
    img.save(path, "JPEG", quality=95)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    tmp = tempfile.mkdtemp(prefix="ogcard_")
    try:
        big = os.path.join(tmp, "big.jpg")
        small = os.path.join(tmp, "small.jpg")
        tall = os.path.join(tmp, "tall.jpg")
        noisy(big, 1800, 1013, 40)
        noisy(small, 600, 400, 40)
        noisy(tall, 1400, 2000, 40)

        logo = os.path.join(tmp, "logo.png")
        lg = Image.new("RGBA", (600, 160), (255, 255, 255, 0))
        for y in range(40, 120):
            for x in range(40, 560):
                lg.putpixel((x, y), (255, 255, 255, 255))
        lg.save(logo)

        out = os.path.join(tmp, "card.jpg")
        rc, txt = run([big, out, "--logo", logo])
        ok("it runs on a large photo", rc == 0, txt.strip()[:60])
        im = Image.open(out)
        ok("the card is exactly 1200x630", im.size == (1200, 630), str(im.size))
        ok("it stays inside the size budget",
           os.path.getsize(out) <= 300 * 1024,
           "%dKB" % (os.path.getsize(out) // 1024))
        ok("it tells you to look at the result", "look at it" in txt)

        # the scrim has to actually darken the bottom, or a logo is unreadable
        top = Image.open(out).crop((0, 0, 1200, 60)).resize((1, 1)).getpixel((0, 0))
        bot = Image.open(out).crop((0, 570, 1200, 630)).resize((1, 1)).getpixel((0, 0))
        ok("the bottom is darker than the top, so a logo can be read",
           sum(bot) < sum(top), "top %d vs bottom %d" % (sum(top), sum(bot)))

        out2 = os.path.join(tmp, "tall.jpg")
        rc, txt = run([tall, out2])
        ok("a portrait photo is still cropped to the right shape",
           rc == 0 and Image.open(out2).size == (1200, 630))

        out3 = os.path.join(tmp, "small-card.jpg")
        rc, txt = run([small, out3])
        ok("a photo too small to use says so rather than quietly blurring",
           "WARNING" in txt and "smaller than" in txt)
        ok("but it still produces a correctly shaped card",
           Image.open(out3).size == (1200, 630))

        rc, txt = run([os.path.join(tmp, "nope.jpg"), out3])
        ok("a missing photo is refused, not invented", rc == 2)

        rc, txt = run([big, out3, "--logo", os.path.join(tmp, "nope.png")])
        ok("a missing logo is refused too", rc == 2)

        rc, txt = run([big, os.path.join(tmp, "tiny.jpg"), "--max-kb", "20"])
        ok("an impossible budget is reported, not silently exceeded",
           rc == 1 and "Still over" in txt)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    bad = RESULTS.count(False)
    print("\n%d/%d checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
