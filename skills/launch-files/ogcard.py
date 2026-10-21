# -*- coding: utf-8 -*-
"""Build a share card from a photo the site already owns.

    python ogcard.py <photo> <out.jpg> [--logo <png>] [--max-kb 300]

Produces exactly 1200x630, the ratio every platform crops to, under a size
budget, with a gradient scrim so a logo stays readable over any photo.

Why this exists: the same defect has now appeared on four sites. A share card
is either missing, or it is a screenshot of the homepage at the wrong ratio,
or it is served from a preview bucket that will stop existing. Every one of
those is invisible until a client shares the link and sees a blank box.

A gradient, not a rectangle. A hard-edged panel behind a logo reads as a box
pasted onto a photo, which is exactly the look this is meant to avoid.
"""
import io, os, sys

try:
    from PIL import Image
except ImportError:
    print("needs Pillow:  pip install Pillow")
    sys.exit(2)

W, H = 1200, 630
SCRIM_TOP = 0.0       # transparent at the top
SCRIM_BOTTOM = 0.62   # to 62% black at the bottom
LOGO_WIDTH = 0.36     # of the card width
LOGO_BASELINE = 0.74  # logo centre sits here down the card


def arg(name, fallback=None):
    i = sys.argv.index("--" + name) if "--" + name in sys.argv else -1
    return sys.argv[i + 1] if i > -1 and i + 1 < len(sys.argv) else fallback


def cover(img, w, h):
    """Fill w x h without distorting, cropping the overflow from the centre."""
    src_ratio, want_ratio = img.width / img.height, w / h
    if src_ratio > want_ratio:
        new_w = int(img.height * want_ratio)
        box = ((img.width - new_w) // 2, 0,
               (img.width - new_w) // 2 + new_w, img.height)
    else:
        new_h = int(img.width / want_ratio)
        box = (0, (img.height - new_h) // 2,
               img.width, (img.height - new_h) // 2 + new_h)
    return img.crop(box).resize((w, h), Image.LANCZOS)


def scrim(card):
    """A smooth vertical darkening, strongest at the bottom."""
    grad = Image.new("L", (1, H))
    for y in range(H):
        t = y / (H - 1)
        grad.putpixel((0, y), int(255 * (SCRIM_TOP + (SCRIM_BOTTOM - SCRIM_TOP)
                                         * (t ** 1.6))))
    mask = grad.resize((W, H))
    return Image.composite(Image.new("RGB", (W, H), (0, 0, 0)), card, mask)


def place_logo(card, logo_path):
    logo = Image.open(logo_path).convert("RGBA")
    want_w = int(W * LOGO_WIDTH)
    logo = logo.resize((want_w, max(1, int(logo.height * want_w / logo.width))),
                       Image.LANCZOS)
    x = (W - logo.width) // 2
    y = int(H * LOGO_BASELINE) - logo.height // 2
    card = card.convert("RGBA")
    card.alpha_composite(logo, (x, max(0, min(y, H - logo.height))))
    return card.convert("RGB")


def save_under(card, out, max_kb):
    """Step the quality down until it fits, and say what it took."""
    for q in (88, 84, 80, 75, 70, 65, 60):
        buf = io.BytesIO()
        card.save(buf, "JPEG", quality=q, optimize=True, progressive=True)
        if buf.tell() <= max_kb * 1024 or q == 60:
            io.open(out, "wb").write(buf.getvalue())
            return q, buf.tell()
    return None, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    skip = set()
    for flag in ("logo", "max-kb"):
        if "--" + flag in sys.argv:
            skip.add(arg(flag))
    args = [a for a in args if a not in skip]
    if len(args) < 2:
        print(__doc__)
        return 2
    photo, out = args[0], args[1]
    if not os.path.isfile(photo):
        print("no such photo: %s" % photo)
        return 2
    logo = arg("logo")
    max_kb = int(arg("max-kb", "300"))

    src = Image.open(photo).convert("RGB")
    if src.width < W or src.height < H:
        print("WARNING: %s is %dx%d, smaller than %dx%d. Upscaling will look "
              "soft. Pick a larger photo if there is one."
              % (os.path.basename(photo), src.width, src.height, W, H))
    card = scrim(cover(src, W, H))
    if logo:
        if not os.path.isfile(logo):
            print("no such logo: %s" % logo)
            return 2
        card = place_logo(card, logo)

    q, size = save_under(card, out, max_kb)
    print("%s  %dx%d  %dKB  quality %d" % (out, W, H, size // 1024, q))
    if size > max_kb * 1024:
        print("Still over %dKB at the lowest quality. Use a simpler photo."
              % max_kb)
        return 1
    print("\nNow look at it. A card that measures correctly can still read "
          "badly: a logo lost against a busy photo, a face cropped in half.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
