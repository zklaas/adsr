#!/usr/bin/env python3
"""Build the ADSR app icon: a fan of four cards behind "ADSR", blue on beige.

Dev tool - needs Pillow (``pip install pillow``).  The game never imports it;
the icon ships as plain PNGs in icons/.

Usage:
    python3 make_icon.py                     use the best free font found
    python3 make_icon.py --font PATH.ttf     use this font file

The lettering wants a rounded geometric face in the Bauhaus spirit, from
free fonts only.  Comfortaa Bold is the closest (sudo apt install
fonts-comfortaa); URW Gothic Demi (fonts-urw-base35, normally installed) is
the fallback.  After rebuilding, run ./install-desktop.sh to refresh the
dash icon.
"""
from __future__ import annotations

import argparse
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icons")

BEIGE = (239, 228, 204)
BLUE = (30, 78, 156)
FACE = (251, 247, 238)
SIZE = 512
RADIUS = 84
TEXT = "ADSR"
# One card per letter, in the game's Waveforms colours: blue, red, amber, green.
CARD_COLOURS = [(59, 127, 196), (196, 71, 63), (208, 138, 30), (63, 154, 90)]

# (glob, variable-font style to select or None), best first.
SEARCH = [
    ("/usr/share/fonts/**/Comfortaa*Bold*.[tTo][tT][fF]", None),
    ("~/.local/share/fonts/**/Comfortaa*Bold*.[tTo][tT][fF]", None),
    ("/usr/share/fonts/**/Comfortaa*.[tTo][tT][fF]", b"Bold"),
    ("~/.local/share/fonts/**/Comfortaa*.[tTo][tT][fF]", b"Bold"),
    ("/usr/share/fonts/**/URWGothic-Demi.[otOT][tT][fF]", None),
    ("/usr/share/fonts/**/URWGothic-Demi.t1", None),
]
STAND_IN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def find_font() -> tuple[str, bytes | None] | None:
    for pat, style in SEARCH:
        hits = sorted(glob.glob(os.path.expanduser(pat), recursive=True))
        if hits:
            return hits[0], style
    return None


def load(path: str, size: int, style: bytes | None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(path, size)
    if style:
        try:
            f.set_variation_by_name(style)
        except (OSError, ValueError):
            pass
    return f


def fit_font(path, style, box_w: int, box_h: int) -> ImageFont.FreeTypeFont:
    """Largest size whose ink for TEXT fits the box."""
    lo, hi = 10, 900
    while lo < hi:
        mid = (lo + hi + 1) // 2
        l, t, r, b = load(path, mid, style).getbbox(TEXT)
        if r - l <= box_w and b - t <= box_h:
            lo = mid
        else:
            hi = mid - 1
    return load(path, lo, style)


def card(w: int, h: int, colour, scale: int) -> Image.Image:
    """One game card: cream face, coloured outline and top band."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(w * 0.11)
    dark = tuple(int(c * 0.7) for c in colour)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=FACE, outline=dark, width=4 * scale)
    m = int(w * 0.07)
    d.rounded_rectangle((m, m, w - 1 - m, m + int(h * 0.2)), int(r * 0.7), fill=colour)
    return img


def build(font_path: str, style) -> Image.Image:
    scale = 4                                   # supersample, then shrink
    S = SIZE * scale
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), RADIUS * scale, fill=BEIGE)
    inset = 26 * scale
    d.rounded_rectangle((inset, inset, S - 1 - inset, S - 1 - inset),
                        (RADIUS - 26) * scale, outline=BLUE, width=7 * scale)

    # A fan of four cards, pivoting on a point below the icon's centre.
    cw, ch = int(S * 0.27), int(S * 0.40)
    pivot = (S / 2, S * 0.80)
    for colour, angle in zip(CARD_COLOURS, (24, 8, -8, -24)):
        c = card(cw, ch, colour, scale)
        layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        top = int(pivot[1] - ch * 1.32)
        layer.paste(c, (int(pivot[0] - cw / 2), top), c)
        img.alpha_composite(layer.rotate(angle, center=pivot,
                                         resample=Image.Resampling.BICUBIC))

    # "ADSR" across the front, with a beige outline so it reads over the cards.
    font = fit_font(font_path, style, int(S * 0.72), int(S * 0.30))
    l, t, r, b = font.getbbox(TEXT)
    x = (S - (r - l)) / 2 - l
    y = S * 0.62 - (b - t) / 2 - t
    d = ImageDraw.Draw(img)
    d.text((x, y), TEXT, font=font, fill=BLUE, stroke_width=9 * scale, stroke_fill=BEIGE)
    return img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--font", help="path to a .ttf/.otf for the lettering")
    a = ap.parse_args()
    if a.font and not os.path.isfile(a.font):
        print(f"make_icon: no such font file: {a.font}", file=sys.stderr)
        return 1
    found = (a.font, None) if a.font else find_font()
    if not found:
        print("make_icon: no Comfortaa or URW Gothic found - using DejaVu Sans Bold.\n"
              "  For the intended look: sudo apt install fonts-comfortaa",
              file=sys.stderr)
        found = (STAND_IN, None)
    os.makedirs(OUT, exist_ok=True)
    big = build(*found)
    big.save(os.path.join(OUT, "adsr.png"))
    for s in (256, 128, 64, 48):
        big.resize((s, s), Image.Resampling.LANCZOS).save(os.path.join(OUT, f"adsr-{s}.png"))
    print(f"icons/adsr.png (+256/128/64/48) built with {os.path.basename(found[0])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
