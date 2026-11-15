#!/usr/bin/env python3
"""Prepare the web version's data: every card emblem as SVG path data (taken
from the desktop version's own drawing code, so both look the same) and the list
of decks.  Run after adding a deck or changing an emblem:

    python3 web/make_web.py

Writes web/glyphs.json and web/manifest.json, and stamps index.html's links
with content versions.  Needs PyQt6 (desktop only).  Run it before publishing
any change to the web files.
"""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from PyQt6.QtCore import QRectF                 # noqa: E402
from PyQt6.QtWidgets import QApplication        # noqa: E402

from app import gui                             # noqa: E402
from app.cards import bundled_decks, load_config  # noqa: E402

# The emblem area on a 108 x 156 card (see gui.paint_card): 60% of the width,
# 15% of the height, just below the coloured band.
CARD_W, CARD_H = 108, 156
GW, GH = CARD_W * 0.6, CARD_H * 0.15


def svg_path(path) -> str:
    out, i, n = [], 0, path.elementCount()
    while i < n:
        e = path.elementAt(i)
        t = e.type.value if hasattr(e.type, "value") else int(e.type)
        if t == 0:
            out.append(f"M{e.x:.2f} {e.y:.2f}")
            i += 1
        elif t == 1:
            out.append(f"L{e.x:.2f} {e.y:.2f}")
            i += 1
        elif t == 2:                                   # cubic: this + two data points
            c2, end = path.elementAt(i + 1), path.elementAt(i + 2)
            out.append(f"C{e.x:.2f} {e.y:.2f} {c2.x:.2f} {c2.y:.2f} {end.x:.2f} {end.y:.2f}")
            i += 3
        else:
            i += 1
    return "".join(out)


def main():
    QApplication.instance() or QApplication([])
    decks = []
    glyphs = {}
    for name, path in bundled_decks():
        cfg = load_config(path)
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        decks.append({"name": name, "file": rel, "max_players": cfg.max_players})
        for k in cfg.kinds:
            if k.glyph != "letter" and k.glyph not in glyphs:
                glyphs[k.glyph] = {"d": svg_path(gui.glyph_path(QRectF(0, 0, GW, GH), k.glyph)),
                                   "icon": k.glyph in gui.ICONS}
    with open(os.path.join(HERE, "glyphs.json"), "w", encoding="utf-8") as f:
        json.dump(glyphs, f, separators=(",", ":"))
    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"decks": decks,
                   "python": ["app/__init__.py", "app/cards.py", "app/engine.py", "app/ai.py"]},
                  f, indent=1)
    stamp_versions()
    print(f"{len(glyphs)} emblems, {len(decks)} decks")


def stamp_versions():
    """Give index.html's links to adsr.css and adsr.js a ?v=<content hash>, so a
    changed file has a new address and browsers fetch it at once instead of
    using a cached copy (GitHub Pages lets browsers keep files for 10 minutes)."""
    import hashlib
    import re
    page = os.path.join(HERE, "index.html")
    html = open(page, encoding="utf-8").read()
    for name in ("adsr.css", "adsr.js"):
        with open(os.path.join(HERE, name), "rb") as f:
            v = hashlib.sha1(f.read()).hexdigest()[:10]
        html = re.sub(re.escape(name) + r'(\?v=[0-9a-f]+)?"', f'{name}?v={v}"', html)
    open(page, "w", encoding="utf-8").write(html)


if __name__ == "__main__":
    main()
