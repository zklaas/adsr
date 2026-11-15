"""The ADSR table (PyQt6): setup, vs-computer, hot-seat and LAN play.

The table only ever draws an engine *view* (a plain dict) and emits actions,
so it works the same whether the engine runs here (LocalSession) or on a LAN
host (RemoteSession).
"""
from __future__ import annotations

import json
import math
import os
import random

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QPointF, QRectF, Qt

from . import ai
from .cards import (DEFAULT_DECK, TYPE_NAMES, ConfigError, bundled_decks, deck_summary,
                    load_config)
from .engine import ASSIST, DEFEND, OVER, SUSTAIN, TURN, Game, GameError
from .net import DEFAULT_PORT, NetClient, NetHost, local_addresses

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICON = os.path.join(APP_DIR, "icons", "adsr.png")
RULES = os.path.join(APP_DIR, "RULES.md")

FELT = "#1e4a35"
FELT_DARK = "#153527"
FELT_LINE = "#2f6a4d"
INK = "#f1efe6"
MUTED = "#a9c2b4"
GOLD = "#f2c14e"
HIT = "#ff8a7a"
SAFE = "#9fe0a8"
CARD_FACE = "#fbf8f0"
SPEEDS = {"Fast": 250, "Normal": 750, "Slow": 1600}
LEVEL_NAMES = {"easy": "Easy", "normal": "Normal", "hard": "Hard"}


# ------------------------------------------------------------------- drawing
def icon_path(r: QRectF, glyph: str) -> QtGui.QPainterPath:
    """Line-art emblems for the families of the themed decks (Rock Paper
    Scissors Lizard Alien, Hatfields and McCoys, Balance of Power, Romeo and Juliet, Captains, Infielders), drawn in units of half the glyph area's height around its centre."""
    path = QtGui.QPainterPath()
    cx, cy, a = r.center().x(), r.center().y(), r.height() / 2
    if glyph in ("hatfield", "mccoy"):  # portraits need more height to read
        a *= 1.3

    def P(x, y):
        return QPointF(cx + x * a, cy + y * a)

    def line(*pts, close=False):
        path.moveTo(P(*pts[0]))
        for q in pts[1:]:
            path.lineTo(P(*q))
        if close:
            path.closeSubpath()

    def ring(x, y, rx, ry=None):
        path.addEllipse(P(x, y), rx * a, (ry if ry is not None else rx) * a)

    if glyph == "rock":            # a lumpy stone with a crack
        line((-.95, .85), (-1.15, .1), (-.7, -.6), (-.1, -.95), (.6, -.75), (1.1, -.1),
             (.9, .85), close=True)
        line((-.1, -.95), (.05, -.25), (.4, .1))
    elif glyph == "paper":         # a sheet with a folded corner and lines of text
        line((-.65, -1), (.3, -1), (.65, -.62), (.65, 1), (-.65, 1), close=True)
        line((.3, -1), (.3, -.62), (.65, -.62))
        for y, x2 in ((-.2, .38), (.2, .38), (.6, .12)):
            line((-.38, y), (x2, y))
    elif glyph == "scissors":      # two finger loops and crossed blades
        ring(-1.15, -.45, .32)
        ring(-1.15, .45, .32)
        line((-.85, -.32), (1.3, .38))
        line((-.85, .32), (1.3, -.38))
    elif glyph == "lizard":        # seen from above: S-curved tail, splayed legs
        line(*[(-2.0 + i * .1, .3 * math.sin(i * .42)) for i in range(13)])   # tail
        ring(.35, 0, .85, .3)                       # body
        ring(1.5, 0, .32, .24)                      # head
        line((.95, -.22), (1.15, -.6), (1.4, -.7))  # front legs reach forward
        line((.95, .22), (1.15, .6), (1.4, .7))
        line((-.25, -.22), (-.4, -.6), (-.7, -.72))  # back legs reach back
        line((-.25, .22), (-.4, .6), (-.7, .72))
    elif glyph == "hatfield":      # dented slouch hat and a long bushy beard
        line((-1.05, -.38), (-.65, -.55), (.65, -.55), (1.05, -.38))       # drooping brim
        line((-.55, -.55), (-.5, -.92), (-.18, -1.02), (0, -.9), (.18, -1.02),
             (.5, -.92), (.55, -.55))                                      # dented crown
        ring(0, -.22, .4, .34)                                             # face
        ring(-.15, -.28, .06)
        ring(.15, -.28, .06)
        line((-.4, -.15), (-.45, .2), (-.3, .45), (-.32, .65), (-.12, .8), (0, .98),
             (.12, .8), (.32, .65), (.3, .45), (.45, .2), (.4, -.15))      # beard
        line((-.15, -.02), (0, .05), (.15, -.02))                          # mouth
    elif glyph == "mccoy":         # flat straw boater, moustache, pipe
        line((-1.1, -.5), (1.1, -.5))                                      # brim
        line((-.5, -.5), (-.5, -.86), (.5, -.86), (.5, -.5))               # low crown
        line((-.5, -.64), (.5, -.64))                                      # hat band
        ring(0, .08, .45, .52)                                             # face
        ring(-.17, -.08, .06)
        ring(.17, -.08, .06)
        line((-.5, .1), (-.28, .28), (0, .18), (.28, .28), (.5, .1))       # moustache
        line((.22, .42), (.8, .52))                                        # pipe stem
        line((.72, .52), (.72, .2), (.95, .2), (.95, .52), close=True)     # pipe bowl
    elif glyph == "column":        # Ionic column: abacus, volutes, fluted shaft, base
        line((-.8, -1), (.8, -1), (.8, -.84), (-.8, -.84), close=True)
        ring(-.6, -.66, .15)
        ring(.6, -.66, .15)
        line((-.45, -.7), (.45, -.7))
        line((-.45, -.62), (-.45, .76))
        line((.45, -.62), (.45, .76))
        for x in (-.15, .15):
            line((x, -.55), (x, .7))
        line((-.68, .76), (.68, .76), (.68, 1), (-.68, 1), close=True)
    elif glyph == "palle":         # Medici arms: a shield with six balls in an orle
        line((-.78, -1), (.78, -1), (.78, .15), (.6, .55), (.3, .85), (0, 1), (-.3, .85),
             (-.6, .55), (-.78, .15), close=True)
        for x, y in ((0, -.65), (-.37, -.3), (.37, -.3), (-.37, .1), (.37, .1), (0, .5)):
            ring(x, y, .14)
    elif glyph == "crown":         # five-pointed crown with pearl tips on a jewelled band
        line((-.85, .6), (.85, .6), (.85, .88), (-.85, .88), close=True)
        line((-.85, .6), (-1.0, -.42), (-.48, .1), (0, -.62), (.48, .1), (1.0, -.42),
             (.85, .6))
        for x, y in ((-1.0, -.56), (0, -.76), (1.0, -.56)):
            ring(x, y, .13)
        for x in (-.45, 0, .45):
            ring(x, .74, .07)
    elif glyph == "quill":         # a quill pen over a treaty signature
        line((-.95, .72), (.95, -1.0))                              # shaft
        line((-.45, .27), (-.25, -.25), (.15, -.7), (.95, -1.0),
             (.55, -.35), (.1, .02), (-.45, .27))                   # vane
        for t in (.3, .5, .7):                                      # barbs
            x, y = -.95 + 1.9 * t, .72 - 1.72 * t
            line((x, y), (x - .2, y - .32))
        line(*[(-.35 + i * .12, .9 + .08 * math.sin(i * 1.3)) for i in range(13)])
    elif glyph == "scales":        # a balance, beam level
        ring(0, -.9, .08)
        line((0, -.82), (0, .82))
        line((-.5, .98), (0, .82), (.5, .98), close=True)
        line((-1.05, -.62), (1.05, -.62))
        for x0 in (-1.05, 1.05):
            line((x0, -.62), (x0 - .32, .18))
            line((x0, -.62), (x0 + .32, .18))
            line((x0 - .4, .18), (x0 - .25, .34), (x0, .4), (x0 + .25, .34),
                 (x0 + .4, .18), close=True)
    elif glyph == "rapier":        # Montagues: two crossed rapiers, points up
        for s in (1, -1):
            ring(-.88 * s, .98, .08)                                # pommel
            line((-.82 * s, .92), (-.55 * s, .62))                  # grip
            line((-.76 * s, .4), (-.34 * s, .84))                   # crossguard
            line((-.55 * s, .62), (.95 * s, -1.0))                  # blade
    elif glyph == "balcony":       # Capulets: an arched window over a balustrade
        line((-.55, .2), *[(-.55 * math.cos(t * math.pi / 12), -.45 - .5 * math.sin(t * math.pi / 12))
                            for t in range(13)], (.55, .2))
        line((0, -.95), (0, .2))                                    # mullion
        line((-1, .2), (1, .2), (1, .34), (-1, .34), close=True)    # balcony floor
        for x in (-.8, -.4, 0, .4, .8):                             # balusters
            line((x, .34), (x, .82))
        line((-1, .82), (1, .82))
    elif glyph == "tower":         # Citizens of Verona: a tower with swallowtail merlons
        line((-.6, -.55), (-.6, -1), (-.45, -.85), (-.3, -1), (-.3, -.75), (-.15, -.75),
             (-.15, -1), (0, -.85), (.15, -1), (.15, -.75), (.3, -.75), (.3, -1),
             (.45, -.85), (.6, -1), (.6, -.55), close=True)
        line((-.45, -.55), (-.45, 1))
        line((.45, -.55), (.45, 1))
        line((-.8, 1), (.8, 1))
        line((-.12, -.05), (-.12, -.3), (0, -.4), (.12, -.3), (.12, -.05), close=True)
        line((-.2, 1), (-.2, .62), (0, .45), (.2, .62), (.2, 1))    # gate
    elif glyph == "ewer":          # Servants: a serving jug with spout and handle
        line((-.3, -.75), (-.35, -.5), (-.6, 0), (-.55, .55), (-.3, .9), (.3, .9),
             (.55, .55), (.6, 0), (.35, -.5), (.3, -.75))
        line((-.3, -.75), (-.85, -.95), (-.38, -.55))               # spout
        line((-.3, -.75), (.3, -.75))                               # rim
        line((.33, -.65), (.8, -.6), (.85, -.15), (.55, .3))        # handle
        line((-.58, .2), (.58, .2))                                 # band
    elif glyph == "chapel":        # Church Figures: a chapel with a cross
        line((0, -1.05), (0, -.6))
        line((-.17, -.88), (.17, -.88))
        line((-.85, -.05), (0, -.6), (.85, -.05))                   # roof
        line((-.65, -.18), (-.65, 1), (.65, 1), (.65, -.18))        # walls
        line((-.2, 1), (-.2, .6), (0, .45), (.2, .6), (.2, 1))      # door
        ring(0, .1, .13)                                            # rose window
    elif glyph == "anchor":        # Mariners: ring, stock, shank, curved arms with flukes
        ring(0, -.86, .14)
        line((-.45, -.55), (.45, -.55))                             # stock
        line((0, -.72), (0, .95))                                   # shank
        line(*[(.8 * math.sin(t * math.pi / 16), .15 + .8 * math.cos(t * math.pi / 16))
               for t in range(-8, 9)])                              # arms
        for s in (1, -1):
            line((.8 * s, .15), (.8 * s, -.1), (.62 * s, .1))       # flukes
    elif glyph == "bars":          # Soldiers: a captain's two collar bars
        for x in (-.85, .2):
            line((x, -.9), (x + .65, -.9), (x + .65, .9), (x, .9), close=True)
            line((x + .325, -.65), (x + .325, .65))
    elif glyph == "wings":         # Aviators: pilot's wings round a central disc
        ring(0, 0, .38)
        for s in (1, -1):
            line((.38 * s, -.1), (1.0 * s, -.45), (2.0 * s, -.7), (1.75 * s, -.3),
                 (1.5 * s, -.32), (1.25 * s, -.02), (.98 * s, -.05), (.75 * s, .22),
                 (.38 * s, .12))                                    # stepped feathers
    elif glyph == "armband":       # Team Captains: an armband with a big C
        line((-1.4, -.65), (1.4, -.8), (1.4, .8), (-1.4, .65), close=True)
        x0, y0 = P(-.5, -.5).x(), P(-.5, -.5).y()
        path.arcMoveTo(x0, y0, a, a, 45)
        path.arcTo(x0, y0, a, a, 45, 270)
    elif glyph == "badge":         # Civic Captains: a shield badge with a star
        line((0, -1), (.75, -.75), (.75, .1), (.45, .6), (0, .95), (-.45, .6), (-.75, .1),
             (-.75, -.75), close=True)
        line(*[(.42 * (1 if i % 2 == 0 else .42) * math.sin(i * math.pi / 5),
                -.08 - .42 * (1 if i % 2 == 0 else .42) * math.cos(i * math.pi / 5))
               for i in range(10)], close=True)
    elif glyph == "bat":           # Yankees: a bat and a ball
        c, s_ = math.cos(math.radians(38)), math.sin(math.radians(38))

        def R(x, y):                                                # along the bat
            return (-1.3 + x * c - y * s_, .95 - x * s_ - y * c)
        ring(*R(-.08, 0), .11)                                      # knob
        line(R(0, -.06), R(1.0, -.07), R(1.8, -.2), R(2.5, -.21), R(2.62, -.12),
             R(2.62, .12), R(2.5, .21), R(1.8, .2), R(1.0, .07), R(0, .06), close=True)
        ring(1.1, .6, .32)                                          # ball
    elif glyph == "baseball":      # Cardinals: a baseball with its two seams
        ring(0, 0, .95)
        for s in (1, -1):
            seam = [(s * (.95 - .38 * math.cos(t * math.pi / 8)), .82 * math.sin(t * math.pi / 8))
                    for t in range(-3, 4)]
            line(*seam)
            for x, y in seam[1:-1]:                                 # stitches
                line((x - .1 * s, y - .06), (x + .1 * s, y + .06))
    elif glyph == "cap":           # Dodgers: a ball cap, side on
        line((-.85, .45), *[(-.85 * math.cos(t * math.pi / 12), .45 - 1.05 * math.sin(t * math.pi / 12))
                             for t in range(13)])                   # crown
        line((-.85, .45), (.85, .45))
        line((.6, .45), (1.25, .5), (1.5, .62), (.75, .7), (.6, .6))   # visor
        ring(0, -.66, .08)                                          # button
        line((0, -.58), (-.15, .45))                                # panel seam
    elif glyph == "scoreboard":    # Red Sox: a tall wall with a hand-worked scoreboard
        line((-1.45, -.9), (1.45, -.9), (1.45, .9), (-1.45, .9), close=True)
        for row in (-.42, .22):
            for x in (-.9, -.3, .3, .9):
                line((x - .2, row - .22), (x + .2, row - .22), (x + .2, row + .22),
                     (x - .2, row + .22), close=True)
    elif glyph == "ivy":           # Cubs: a three-lobed Boston ivy leaf, as on Wrigley's wall
        tips = ((-1.05, -.15), (0, -1.0), (1.05, -.15))
        line((0, .5), (-.45, .6), (-.85, .4), tips[0], (-.6, -.45), (-.3, -.35), tips[1],
             (.3, -.35), (.6, -.45), tips[2], (.85, .4), (.45, .6), close=True)
        for x, y in tips:                                           # veins
            line((0, .4), (x * .75, .4 + (y - .4) * .75))
        line((0, .5), (.1, .78), (.35, .98))                        # stem
    else:                        # alien: domed head, antennae, three tentacles
        ring(0, -.3, .75, .55)
        line((-.3, -.82), (-.65, -1.15))
        line((.3, -.82), (.65, -1.15))
        ring(-.3, -.35, .12)
        ring(.3, -.35, .12)
        for x0 in (-.5, 0, .5):
            line(*[(x0 + .15 * math.sin(i * 1.4), .25 + i * .19) for i in range(5)])
    return path


ICONS = ("rock", "paper", "scissors", "lizard", "alien", "hatfield", "mccoy",
         "column", "palle", "crown", "quill", "scales", "rapier", "balcony", "tower",
         "ewer", "chapel", "anchor", "bars", "wings", "armband", "badge", "bat", "baseball",
         "cap", "scoreboard", "ivy")


def glyph_path(r: QRectF, glyph: str) -> QtGui.QPainterPath:
    if glyph in ICONS:
        return icon_path(r, glyph)
    path = QtGui.QPainterPath()
    x0, w, cy, a = r.left(), r.width(), r.center().y(), r.height() / 2
    if glyph == "sine":
        pts = [(i / 48, -math.sin(2 * math.pi * i / 48)) for i in range(49)]
    elif glyph == "cosine":
        pts = [(i / 48, -math.cos(2 * math.pi * i / 48)) for i in range(49)]
    elif glyph == "square":
        pts = [(0, 0), (0, -1), (.5, -1), (.5, 1), (1, 1), (1, 0)]
    elif glyph == "pulse":
        pts = [(0, 1), (.1, 1), (.1, -1), (.3, -1), (.3, 1), (.6, 1), (.6, -1),
               (.8, -1), (.8, 1), (1, 1)]
    elif glyph == "ramp":          # one long rise and a drop
        pts = [(0, 1), (.85, -1), (.85, 1), (1, 1)]
    elif glyph == "saw":
        pts = [(0, 0), (.5, -1), (.5, 1), (1, 0)]
    elif glyph == "reverse saw":
        pts = [(0, 0), (0, -1), (.5, 1), (.5, -1), (1, 1), (1, 0)]
    elif glyph == "noise":         # fixed jagged line, the same on every card
        ys = [0, -.7, .4, -.2, .9, -.9, .3, .6, -.5, .1, -.8, .7, -.3, .5, 0]
        pts = [(i / (len(ys) - 1), y) for i, y in enumerate(ys)]
    elif glyph == "wavetable":     # a few harmonics summed
        pts = [(i / 64, -(math.sin(2 * math.pi * i / 64) + .5 * math.sin(6 * math.pi * i / 64)
                          + .3 * math.sin(10 * math.pi * i / 64)) / 1.25) for i in range(65)]
    else:  # triangle
        pts = [(0, 0), (.25, -1), (.75, 1), (1, 0)]
    path.moveTo(QPointF(x0 + pts[0][0] * w, cy + pts[0][1] * a))
    for x, y in pts[1:]:
        path.lineTo(QPointF(x0 + x * w, cy + y * a))
    return path


def _font(px: float, bold=False) -> QtGui.QFont:
    f = QtGui.QFont()
    f.setPixelSize(max(7, int(px)))
    f.setBold(bold)
    return f


def paint_card(p: QtGui.QPainter, r: QRectF, card: dict, kinds: list,
               selected=False, dim=False, small=False) -> None:
    kind = kinds[card["kind"]]
    col = QtGui.QColor(kind["color"])
    p.save()
    p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    if dim:
        p.setOpacity(0.38)
    rad = r.width() * 0.09
    p.setPen(QtGui.QPen(QtGui.QColor(GOLD) if selected else col.darker(140),
                        3.4 if selected else 1.4))
    p.setBrush(QtGui.QColor(CARD_FACE))
    p.drawRoundedRect(r.adjusted(1.5, 1.5, -1.5, -1.5), rad, rad)

    inset = 4 if not small else 3
    band = QRectF(r.left() + inset, r.top() + inset, r.width() - 2 * inset,
                  r.height() * (0.25 if small else 0.22))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(col)
    p.drawRoundedRect(band, rad * 0.7, rad * 0.7)
    p.setPen(QtGui.QColor("white"))
    p.setFont(_font(band.height() * 0.68, True))
    p.drawText(band.adjusted(band.width() * 0.08, 0, 0, 0),
               Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, card["type"])
    if kind.get("head"):                        # head of the family
        p.setFont(_font(band.height() * 0.6, True))
        p.drawText(band, Qt.AlignmentFlag.AlignCenter, "★")
    elif card["type"] in kind.get("wild", ""):   # answers an Attack of any Kind
        p.setFont(_font(band.height() * (0.5 if small else 0.42), True))
        p.drawText(band, Qt.AlignmentFlag.AlignCenter, "✱" if small else "WILD")
    if card["need"] > 1:
        p.setFont(_font(band.height() * 0.42, True))
        p.drawText(band.adjusted(0, 0, -band.width() * 0.08, 0),
                   Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"×{card['need']}")

    g = QRectF(r.left() + r.width() * 0.2, band.bottom() + r.height() * (0.07 if small else 0.05),
               r.width() * 0.6, r.height() * 0.15)
    if kind["glyph"] == "letter":
        p.setPen(col)
        p.setFont(_font(g.height() * 1.2, True))
        p.drawText(g, Qt.AlignmentFlag.AlignCenter, kind["name"][:1].upper())
    else:
        pen = QtGui.QPen(col, max(1.4 if kind["glyph"] in ICONS else 1.6,
                                  r.width() * (0.024 if kind["glyph"] in ICONS else 0.035)))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(glyph_path(g, kind["glyph"]))

    y = g.bottom() + r.height() * (0.05 if small else 0.03)
    ink = col.darker(165)
    if not small:
        p.setPen(ink)
        f = _font(r.height() * 0.082, True)
        room = r.width() - 8
        wide = QtGui.QFontMetricsF(f).horizontalAdvance(kind["name"])
        if wide > room:                             # shrink long Kind names to fit
            f = _font(r.height() * 0.082 * room / wide, True)
        p.setFont(f)
        p.drawText(QRectF(r.left(), y, r.width(), r.height() * 0.1),
                   Qt.AlignmentFlag.AlignCenter, kind["name"])
        p.setFont(_font(r.height() * 0.075))
        p.drawText(QRectF(r.left(), y + r.height() * 0.09, r.width(), r.height() * 0.1),
                   Qt.AlignmentFlag.AlignCenter, TYPE_NAMES[card["type"]])
        y += r.height() * 0.17
    p.setPen(QtGui.QColor("#26241f"))
    p.setFont(_font(r.height() * (0.17 if small else 0.14), True))
    vr = QRectF(r.left(), y, r.width(), r.height() * (0.19 if small else 0.16))
    p.drawText(vr, Qt.AlignmentFlag.AlignCenter, f"{card['value']}%")
    if card["type"] == "A":
        p.setPen(QtGui.QColor("#a8322a"))
        p.setFont(_font(r.height() * (0.11 if small else 0.09), True))
        p.drawText(QRectF(r.left(), vr.bottom() - r.height() * (0.02 if small else 0.01),
                          r.width(), r.height() * (0.12 if small else 0.1)),
                   Qt.AlignmentFlag.AlignCenter, f"{card['damage']} dmg")
    p.restore()


def has_families(kinds: list) -> bool:
    return len({k.get("family", k["name"]) for k in kinds}) < len(kinds)


def family_names(kinds: list, k: int) -> list[str]:
    fam = kinds[k].get("family", kinds[k]["name"])
    return [x["name"] for x in kinds if x.get("family", x["name"]) == fam]


def or_list(items: list[str], word="or") -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} {word} {items[-1]}"


def match_phrase(kinds: list, k: int) -> str:
    """Which Kinds may answer an Attack of Kind k, as rich text."""
    if not has_families(kinds):
        return f"the <span style='color:{kinds[k]['color']}'><b>{kinds[k]['name']}</b></span> Kind"
    members = [f"<span style='color:{x['color']}'>{x['name']}</span>" for x in kinds
               if x.get("family") == kinds[k].get("family")]
    return f"the <b>{kinds[k]['family']}</b> family ({or_list(members)})"


def beaters(kinds: list, k: int) -> list[str]:
    """Families that beat Kind k's family (their Decays/Releases answer it)."""
    fam = kinds[k].get("family")
    return sorted({x["family"] for x in kinds if fam in x.get("beats", {})})


def beat_phrase(kinds: list, k: int, types: str, bonus: int) -> str:
    """' — or a Decay from Rock or Alien (+15%)', or '' when nothing beats it."""
    fams = beaters(kinds, k)
    if not fams:
        return ""
    return (f" — or {types} from <b>{or_list(fams)}</b>, which beat "
            f"{kinds[k]['family']} (+{bonus}%)")


def is_wild(kinds: list, typ: str) -> bool:
    """Do cards of type `typ` answer an Attack of any Kind in this deck?"""
    return bool(kinds) and typ in kinds[0].get("wild", "")


def wild_phrase(kinds: list, k: int, typ: str, what: str) -> str:
    """'a Decay set of any Kind' when wild, else 'a Decay set from <family>'."""
    if is_wild(kinds, typ):
        return f"{what} of <b>any Kind</b>"
    return f"{what} from {match_phrase(kinds, k)}"


def card_tip(card: dict, kinds: list) -> str:
    name = f"{kinds[card['kind']]['name']} {TYPE_NAMES[card['type']]}"
    bits = [f"<b>{name}</b> — {card['value']}%"]
    if is_wild(kinds, card["type"]):
        bits.append(f"<b>Wild:</b> works on an Attack of any Kind")
    if has_families(kinds):
        fam = kinds[card["kind"]]["family"]
        bits.append(f"{fam} family" + ("" if card["type"] == "A" or is_wild(kinds, card["type"])
                    else f": works on {or_list(family_names(kinds, card['kind']))} Attacks"))
        beats = kinds[card["kind"]].get("beats", {})
        if beats:
            bits.append(" · ".join(f"{fam} {verb} {v}" for v, verb in beats.items())
                        + (" — so this card also answers those Attacks, with a bonus"
                           if card["type"] in "DR" else ""))
    if kinds[card["kind"]].get("head"):
        bits.append(f"★ Head of the {kinds[card['kind']]['family']} family: its Attacks hit "
                    "harder, and whoever stops one draws extra cards")
    if card["type"] == "A":
        bits.append(f"{card['damage']} damage")
    if card["need"] > 1:
        bits.append(f"must be played in a set of exactly {card['need']} {name} cards")
    else:
        bits.append("can be played alone")
    return "<br>".join(bits)


class CardWidget(QtWidgets.QWidget):
    clicked = QtCore.pyqtSignal(int)
    doubleClicked = QtCore.pyqtSignal(int)

    def __init__(self, card: dict, kinds: list, small=False, selected=False, dim=False,
                 width: int | None = None, parent=None):
        super().__init__(parent)
        self.card, self.kinds = card, kinds
        self.small, self.selected, self.dim = small, selected, dim
        if small:
            self.setFixedSize(60, 88)
        else:
            w = width or 108
            self.setFixedSize(w, round(w * 156 / 108))
        self.setToolTip(card_tip(card, kinds))
        if not small:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _e):
        p = QtGui.QPainter(self)
        r = QRectF(self.rect())
        lift = round(self.height() * 0.064)
        if self.selected and not self.small:
            r = r.adjusted(0, 0, 0, -lift)      # lift the selected card
        elif not self.small:
            r = r.adjusted(0, lift, 0, 0)
        paint_card(p, r, self.card, self.kinds, self.selected, self.dim, self.small)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.card["id"])

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.doubleClicked.emit(self.card["id"])


def clear_layout(lay: QtWidgets.QLayout) -> None:
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            clear_layout(item.layout())


# ------------------------------------------------------------------- widgets
class PlayerBox(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("playerBox")
        self.setMinimumWidth(170)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        self.name = QtWidgets.QLabel()
        self.name.setStyleSheet("font-weight: bold; font-size: 15px;")
        self.role = QtWidgets.QLabel()
        self.role.setStyleSheet(f"color: {MUTED};")
        self.hp = QtWidgets.QProgressBar()
        self.hp.setTextVisible(True)
        self.hp.setFixedHeight(18)
        self.info = QtWidgets.QLabel()
        for w in (self.name, self.role, self.hp, self.info):
            lay.addWidget(w)

    def show_player(self, pl: dict, label: str, current: bool, pending: bool, you: bool):
        self.name.setText(pl["name"] + ("  (you)" if you else ""))
        self.role.setText(label)
        self.hp.setMaximum(pl["max_hp"])
        self.hp.setValue(max(0, pl["hp"]))
        self.hp.setFormat(f"{pl['hp']} / {pl['max_hp']} HP")
        frac = pl["hp"] / max(1, pl["max_hp"])
        chunk = "#4fb36b" if frac > 0.5 else "#d9a63a" if frac > 0.25 else "#d2533f"
        self.hp.setStyleSheet(
            f"QProgressBar {{ background: {FELT_DARK}; border: 1px solid {FELT_LINE};"
            f" border-radius: 4px; color: {INK}; text-align: center; }}"
            f"QProgressBar::chunk {{ background: {chunk}; border-radius: 3px; }}")
        if not pl["alive"]:
            self.info.setText("Out")
        else:
            state = "  ·  attacking" if current else ""
            if pending and not current:
                state = "  ·  to respond"
            elif pending and current:
                state = "  ·  to play"
            self.info.setText(f"{pl['hand_count']} cards{state}")
        border = GOLD if pending else (INK if current else FELT_LINE)
        self.setStyleSheet(
            f"#playerBox {{ background: {FELT_DARK}; border: 2px solid {border};"
            f" border-radius: 8px; }}"
            + ("#playerBox QLabel { color: #6f8a7c; }" if not pl["alive"] else ""))


class ExchangeView(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QtWidgets.QVBoxLayout(self)
        self.lay.setContentsMargins(12, 10, 12, 10)
        self.lay.setSpacing(6)

    def _row(self, title: str, cards: list, kinds: list, detail: str):
        row = QtWidgets.QHBoxLayout()
        lab = QtWidgets.QLabel(title)
        lab.setFixedWidth(180)
        lab.setWordWrap(True)
        row.addWidget(lab)
        for c in cards:
            row.addWidget(CardWidget(c, kinds, small=True))
        det = QtWidgets.QLabel(detail)
        det.setStyleSheet("font-size: 14px;")
        row.addSpacing(8)
        row.addWidget(det)
        row.addStretch(1)
        self.lay.addLayout(row)

    def show_view(self, v: dict):
        clear_layout(self.lay)
        ex = v["exchange"] or v["last"]
        kinds = v["deck"]["kinds"]
        names = [p["name"] for p in v["players"]]
        if not ex:
            lab = QtWidgets.QLabel("No Attack yet this game.")
            lab.setStyleSheet(f"color: {MUTED}; font-size: 15px;")
            self.lay.addWidget(lab)
            self.lay.addStretch(1)
            return
        live = v["exchange"] is not None
        kname = kinds[ex["kind"]]["name"]
        if has_families(kinds):
            kname += f" <span style='color:{MUTED}'>({kinds[ex['kind']]['family']})</span>"
        head = QtWidgets.QLabel(
            f"{'' if live else 'Last exchange · '}Turn {ex['turn_no']}: "
            f"<b>{names[ex['attacker']]}</b> attacks <b>{names[ex['target']]}</b> "
            f"<span style='color:{kinds[ex['kind']]['color']}'>■</span> {kname}")
        head.setStyleSheet("font-size: 16px;")
        self.lay.addWidget(head)
        self._row(f"{names[ex['attacker']]}<br><span style='color:{MUTED}'>Attack</span>",
                  ex["cards"], kinds, f"{ex['value']}%  ·  {ex['damage']} damage")
        role_txt = {"target": "defends", "bystander": "joins in", "attacker": "sustains"}
        for pl in ex["plays"]:
            if pl["type"] == "R":
                det = f"{pl['value']}% to release the Attack"
            else:
                sign = "+" if pl["type"] == "S" else "−"
                det = f"{pl['value']}%  →  {sign}{pl['shift']} to the Attack"
            self._row(f"{names[pl['player']]}<br><span style='color:{MUTED}'>"
                      f"{role_txt[pl['role']]} · {TYPE_NAMES[pl['type']]}</span>",
                      pl["cards"], kinds, det)
        pct = QtWidgets.QLabel(f"Chance to hit: <b>{ex['percent']}%</b>")
        pct.setStyleSheet("font-size: 17px;")
        self.lay.addWidget(pct)
        res = ex["result"]
        if res:
            lines = []
            rel = next((p for p in ex["plays"] if p["type"] == "R"), None)
            if res["release_roll"] is not None:
                lines.append(f"Release roll <b>{res['release_roll']}</b> vs {rel['value']}%"
                             f" — {'released!' if res['released'] else 'failed'}")
            if res["attack_roll"] is not None:
                lines.append(f"Attack roll <b>{res['attack_roll']}</b> vs {res['percent']}%"
                             f" — {'hit' if res['hit'] else 'miss'}")
            if res["hit"]:
                total = res["damage"] + sum(x["amount"] for x in res["extras"])
                out = (f"<span style='color:{HIT}'><b>{names[ex['target']]} loses "
                       f"{total} HP</b></span>")
                for x in res["extras"]:
                    out += f"<br>{names[x['player']]}'s Sustain added {x['amount']}"
            else:
                out = f"<span style='color:{SAFE}'><b>{names[ex['target']]} is unharmed</b></span>"
                for x in res["heals"]:
                    out += f"<br>{names[x['player']]} heals {x['amount']} for their Decay"
            if res["eliminated"]:
                out += f"<br><span style='color:{HIT}'><b>{names[ex['target']]} is out!</b></span>"
            lab = QtWidgets.QLabel("<br>".join(lines + [out]))
            lab.setStyleSheet("font-size: 15px;")
            self.lay.addWidget(lab)
        self.lay.addStretch(1)


class TableWidget(QtWidgets.QWidget):
    action = QtCore.pyqtSignal(dict)
    newGame = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view: dict | None = None
        self.selected: set[int] = set()
        self._key = None
        self._log_text = None

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        self.players_row = QtWidgets.QHBoxLayout()
        self.players_row.setSpacing(10)
        outer.addLayout(self.players_row)
        self.boxes: list[PlayerBox] = []

        split = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.exch = ExchangeView()
        sc = QtWidgets.QScrollArea()
        sc.setWidget(self.exch)
        sc.setWidgetResizable(True)
        sc.setObjectName("exchScroll")
        split.addWidget(sc)
        self.log = QtWidgets.QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setObjectName("log")
        split.addWidget(self.log)
        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        split.setSizes([700, 420])
        outer.addWidget(split, 1)

        self.prompt = QtWidgets.QLabel()
        self.prompt.setWordWrap(True)
        self.prompt.setTextFormat(Qt.TextFormat.RichText)
        self.prompt.setStyleSheet("font-size: 15px;")
        outer.addWidget(self.prompt)

        ctl = QtWidgets.QHBoxLayout()
        self.target_lab = QtWidgets.QLabel("Target:")
        self.target = QtWidgets.QComboBox()
        self.target.setMinimumWidth(150)
        self.primary = QtWidgets.QPushButton()
        self.secondary = QtWidgets.QPushButton()
        self.swap = QtWidgets.QPushButton()
        self.swap.setToolTip("Trade dimmed cards (ones you can't play this turn) for new "
                             "ones from the draw pile. Your turn goes on.")
        for b in (self.primary, self.secondary, self.swap):
            b.setMinimumHeight(32)
            b.setMinimumWidth(150)
        self.primary.setObjectName("primary")
        self.hint = QtWidgets.QLabel()
        self.hint.setStyleSheet(f"color: {MUTED};")
        self.pile = QtWidgets.QLabel()
        self.pile.setStyleSheet(f"color: {MUTED};")
        for w in (self.target_lab, self.target, self.primary, self.secondary, self.swap,
                  self.hint):
            ctl.addWidget(w)
        ctl.addStretch(1)
        ctl.addWidget(self.pile)
        outer.addLayout(ctl)

        self.hand_host = QtWidgets.QWidget()
        self.hand_lay = QtWidgets.QHBoxLayout(self.hand_host)
        self.hand_lay.setContentsMargins(4, 0, 4, 4)
        self.hand_lay.setSpacing(8)
        hs = self.hand_scroll = QtWidgets.QScrollArea()
        hs.setWidget(self.hand_host)
        hs.setWidgetResizable(True)
        hs.setFixedHeight(182)
        hs.setObjectName("handScroll")
        outer.addWidget(hs)

        self.primary.clicked.connect(self._primary)
        self.secondary.clicked.connect(self._secondary)
        self.swap.clicked.connect(lambda: self.action.emit(
            {"type": "swap", "cards": sorted(self.selected)}))
        self.target.currentIndexChanged.connect(lambda _i: self._controls())

    # ---------------------------------------------------------------- state
    def mine(self) -> bool:
        v = self.view
        return bool(v) and v["phase"] != OVER and v["you"] is not None and v["pending"] == v["you"]

    def hand(self) -> dict[int, dict]:
        return {c["id"]: c for c in self.view["hand"]} if self.view else {}

    def phase_types(self) -> str:
        return "".join(self.view["legal"].keys()) if self.mine() else ""

    def usable(self) -> set[int]:
        out = set()
        if self.mine():
            for sets in self.view["legal"].values():
                for s in sets:
                    out.update(s)
        return out

    def _is_set(self, ids, typ) -> bool:
        return sorted(ids) in [sorted(s) for s in self.view["legal"].get(typ, [])]

    def _split(self) -> dict[str, list]:
        hand = self.hand()
        parts: dict[str, list] = {}
        for i in sorted(self.selected):
            parts.setdefault(hand[i]["type"], []).append(i)
        return parts

    # --------------------------------------------------------------- update
    def set_view(self, v: dict):
        self.view = v
        key = (v["turn_no"], v["phase"], v["pending"], v["you"])
        if key != self._key:
            self.selected.clear()
            self._key = key
        self.selected &= set(self.hand())
        self._players()
        self.exch.show_view(v)
        text = "\n".join(v["log"])
        if text != self._log_text:
            self._log_text = text
            self.log.setPlainText(text)
            self.log.verticalScrollBar().setValue(self.log.verticalScrollBar().maximum())
        self.pile.setText(f"Draw pile {v['draw_count']}  ·  discards {v['discard_count']}")
        self._hand()
        self._controls()

    def _players(self):
        v = self.view
        while len(self.boxes) < len(v["players"]):
            b = PlayerBox()
            self.boxes.append(b)
            self.players_row.addWidget(b)
        labels = v.get("labels") or [""] * len(v["players"])
        for b, pl in zip(self.boxes, v["players"]):
            b.show_player(pl, labels[pl["id"]], pl["id"] == v["current"] and v["phase"] != OVER,
                          pl["id"] == v["pending"], pl["id"] == v["you"])

    def _hand(self):
        clear_layout(self.hand_lay)
        v = self.view
        kinds = v["deck"]["kinds"]
        usable = self.usable()
        free = self.mine() and v["phase"] == TURN    # any card may be discarded
        if not v["hand"]:
            lab = QtWidgets.QLabel("Hand hidden." if v["you"] is None else "No cards in hand.")
            lab.setStyleSheet(f"color: {MUTED};")
            self.hand_lay.addWidget(lab)
        width = self._card_width(len(v["hand"]))
        for c in v["hand"]:
            dim = self.mine() and c["id"] not in usable
            w = CardWidget(c, kinds, selected=c["id"] in self.selected, dim=dim, width=width)
            if self.mine() and (free or c["id"] in usable):
                w.clicked.connect(self._toggle)
                w.doubleClicked.connect(self._autoset)
            self.hand_lay.addWidget(w)
        self.hand_lay.addStretch(1)

    def _card_width(self, n: int) -> int:
        """Shrink the cards so a whole hand fits across without scrolling."""
        if n == 0:
            return 108
        avail = self.hand_scroll.viewport().width() - 12
        spacing = self.hand_lay.spacing()
        return max(72, min(108, (avail - spacing * (n - 1)) // n))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self.view and self.view["hand"]:
            QtCore.QTimer.singleShot(0, self._hand)

    def _toggle(self, cid: int):
        self.selected ^= {cid}
        self._hand()
        self._controls()

    def _autoset(self, cid: int):
        """Double-click: select the strongest legal set containing that card."""
        hand = self.hand()
        typ = hand[cid]["type"]
        sets = [s for s in self.view["legal"].get(typ, []) if cid in s]
        if not sets:
            return
        best = max(sets, key=lambda s: (sum(hand[i]["value"] + 3 * hand[i]["damage"]
                                            for i in s) / len(s), len(s)))
        if self.view["phase"] == DEFEND:   # keep the other half of a D+R reply
            keep = {i for i in self.selected if hand[i]["type"] != typ}
            self.selected = keep | set(best)
        else:
            self.selected = set(best)
        self._hand()
        self._controls()

    def _controls(self):
        v = self.view
        if not v:
            return
        names = [p["name"] for p in v["players"]]
        mine = self.mine()
        show_target = mine and v["phase"] == TURN
        self.target_lab.setVisible(show_target)
        self.target.setVisible(show_target)
        self.primary.setVisible(True)
        self.secondary.setVisible(mine)
        self.swap.setVisible(False)
        self.hint.setText("")
        n = len(self.selected)

        if v["phase"] == OVER:
            w = v["winners"]
            txt = (f"★ <b>{' & '.join(names[i] for i in w)}</b> "
                   f"win{'s' if len(w) == 1 else ''}! ★" if w else "Game over.")
            self.prompt.setText(txt)
            self.primary.setText("New game…")
            self.primary.setEnabled(True)
            self.secondary.setVisible(False)
            return
        if not mine:
            pend = v["pending"]
            verb = {TURN: "take a turn", DEFEND: "respond", ASSIST: "decide whether to join in",
                    SUSTAIN: "decide on a Sustain"}[v["phase"]]
            self.prompt.setText(f"Waiting for <b>{names[pend]}</b> to {verb}…")
            self.primary.setVisible(False)
            return

        ex = v["exchange"]
        kinds = v["deck"]["kinds"]
        if ex:
            kname = kinds[ex["kind"]]["name"]
            kc = kinds[ex["kind"]]["color"]
            kn = f"<span style='color:{kc}'><b>{kname}</b></span>"
            match = match_phrase(kinds, ex["kind"])
            bonus = v["deck"]["rules"].get("beat_bonus", 0)
        parts = self._split()
        if v["phase"] == TURN:
            self.prompt.setText(
                "<b>Your turn.</b> Select an Attack set — same Kind, and exactly as many "
                "cards as the largest ×N among them — choose a target and Attack. "
                f"Or discard up to {v['deck']['rules']['max_discard']} cards (none = pass). "
                "Double-click a card to pick its best set."
                + (f" First you may <b>swap</b> up to {v['swap']} dimmed card"
                   f"{'s' * (v['swap'] > 1)} for new ones." if v.get("swap") else ""))
            cur = self.target.currentData()
            self.target.blockSignals(True)
            self.target.clear()
            for p in v["players"]:
                if p["alive"] and p["id"] != v["you"]:
                    self.target.addItem(f"{p['name']} ({p['hp']} HP)", p["id"])
            i = self.target.findData(cur)
            self.target.setCurrentIndex(max(0, i))
            self.target.blockSignals(False)
            ok = n > 0 and self._is_set(self.selected, "A")
            self.primary.setText("Attack")
            self.primary.setEnabled(ok and self.target.count() > 0)
            if ok:
                hand = self.hand()
                val = round(sum(hand[i]["value"] for i in self.selected) / n + 1e-9)
                self.hint.setText(f"{val}% to hit · {sum(hand[i]['damage'] for i in self.selected)} damage")
            elif n and "A" in parts and len(parts) == 1:
                self.hint.setText("Not a complete Attack set yet.")
            md = v["deck"]["rules"]["max_discard"]
            self.secondary.setText(f"Discard {n}" if n else "Pass")
            self.secondary.setEnabled(n <= md)
            if n > md:
                self.hint.setText(f"You can discard at most {md}.")
            sw = v.get("swap", 0)
            if sw:
                dimmed = not (self.selected & self.usable())
                self.swap.setVisible(True)
                self.swap.setText(f"Swap {n}" if n else "Swap…")
                self.swap.setEnabled(0 < n <= sw and dimmed)
                if n and not dimmed:
                    self.hint.setText("Only dimmed cards can be swapped.")
                elif n > sw:
                    self.hint.setText(f"You can swap at most {sw}.")
        elif v["phase"] == DEFEND:
            self.prompt.setText(
                f"<b>{names[ex['attacker']]}</b> attacks you with {kn} — "
                f"{ex['percent']}% to hit, {ex['damage']} damage. "
                + (f"Answer with {wild_phrase(kinds, ex['kind'], 'D', 'a Decay set')} "
                   f"(lowers the chance) and/or "
                   f"{wild_phrase(kinds, ex['kind'], 'R', 'a Release set')} (a roll to cancel it)"
                   if is_wild(kinds, "D") or is_wild(kinds, "R") else
                   f"Answer with a Decay set (lowers the chance) and/or a Release set "
                   f"(a roll to cancel it) from {match}")
                + f"{beat_phrase(kinds, ex['kind'], 'Decay/Release', bonus)}.")
            ok = bool(parts) and set(parts) <= {"D", "R"} and all(
                self._is_set(ids, t) for t, ids in parts.items())
            self.primary.setText("Respond")
            self.primary.setEnabled(ok)
            self.secondary.setText("No response")
            self.secondary.setEnabled(True)
        elif v["phase"] == ASSIST:
            self.prompt.setText(
                f"<b>{names[ex['attacker']]}</b> attacks <b>{names[ex['target']]}</b> with {kn} "
                f"({ex['percent']}% to hit). "
                + (f"Join in with {wild_phrase(kinds, ex['kind'], 'S', 'one Sustain set')} — "
                   f"if it hits you deal a share of the damage — or "
                   f"{wild_phrase(kinds, ex['kind'], 'D', 'one Decay set')} — if it fails you heal"
                   if is_wild(kinds, "S") or is_wild(kinds, "D") else
                   f"Join in with one Sustain set — if it hits you deal a share of the damage "
                   f"— or one Decay set — if it fails you heal — from {match}")
                + f"{beat_phrase(kinds, ex['kind'], 'a Decay', bonus)}.")
            typ = next(iter(parts)) if len(parts) == 1 else None
            ok = typ in ("S", "D") and self._is_set(self.selected, typ)
            self.primary.setText(f"Play {TYPE_NAMES[typ]}" if typ in ("S", "D") else "Play")
            self.primary.setEnabled(ok)
            self.secondary.setText("Stay out")
            self.secondary.setEnabled(True)
        else:  # SUSTAIN
            self.prompt.setText(
                f"Your Attack on <b>{names[ex['target']]}</b> stands at {ex['percent']}%. "
                f"Add {wild_phrase(kinds, ex['kind'], 'S', 'a Sustain set')} to raise it, "
                "or resolve now.")
            ok = n > 0 and self._is_set(self.selected, "S")
            self.primary.setText("Play Sustain")
            self.primary.setEnabled(ok)
            self.secondary.setText("Resolve")
            self.secondary.setEnabled(True)

    def _primary(self):
        v = self.view
        if v["phase"] == OVER:
            self.newGame.emit()
            return
        ids = sorted(self.selected)
        if v["phase"] == TURN:
            self.action.emit({"type": "attack", "cards": ids, "target": self.target.currentData()})
        elif v["phase"] == DEFEND:
            self.action.emit({"type": "respond", "cards": ids})
        elif v["phase"] == ASSIST:
            self.action.emit({"type": "assist", "cards": ids})
        else:
            self.action.emit({"type": "sustain", "cards": ids})

    def _secondary(self):
        v = self.view
        ids = sorted(self.selected)
        if v["phase"] == TURN:
            self.action.emit({"type": "discard", "cards": ids})
        else:
            typ = {DEFEND: "respond", ASSIST: "assist", SUSTAIN: "sustain"}[v["phase"]]
            self.action.emit({"type": typ, "cards": []})


# ------------------------------------------------------------------ sessions
class LocalSession(QtCore.QObject):
    """The engine runs here; seats are humans at this screen, computer
    players, or (when hosting) LAN players."""

    def __init__(self, win, cfg, seats: list[dict], host: NetHost | None = None):
        super().__init__(win)
        self.win, self.cfg, self.seats, self.host = win, cfg, seats, host
        self.game = Game(cfg, [s["name"] for s in seats], first=random.randrange(len(seats)))
        self.rng = random.Random()
        self.humans = [i for i, s in enumerate(seats) if s["kind"] == "human"]
        self.hotseat = len(self.humans) > 1
        # Whose hand is on screen.  Hot-seat shows no hand between humans.
        self.viewer = self.humans[0] if len(self.humans) == 1 else None
        self.last_human = None
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._ai_move)
        self._seen_last = None
        if host:
            host.action.connect(self.remote_action)
            host.left.connect(self.remote_left)

    def labels(self, viewer) -> list[str]:
        out = []
        for i, s in enumerate(self.seats):
            if s["kind"] == "ai":
                out.append(f"Computer · {LEVEL_NAMES[s['level']]}")
            elif s["kind"] == "remote":
                out.append("Over the LAN" if i != viewer else "You · over the LAN")
            elif viewer is not None and self.seats[viewer]["kind"] == "remote":
                out.append("At the host's screen")
            else:
                out.append("Human")
        return out

    def push(self):
        v = self.game.view(self.viewer)
        v["labels"] = self.labels(self.viewer)
        self.win.show_table(v)
        if self.host:
            for i, s in enumerate(self.seats):
                if s["kind"] == "remote":
                    hv = self.game.view(i)
                    hv["labels"] = self.labels(i)
                    self.host.send(i, {"t": "view", "view": hv})

    def start(self):
        self.step()

    def step(self):
        self.timer.stop()
        pend = self.game.pending
        if pend is None:
            if self.hotseat:
                self.viewer = None
            self.push()
            return
        pid, _phase = pend
        kind = self.seats[pid]["kind"]
        if kind == "human" and self.hotseat:
            if self.last_human != pid:
                self.viewer = None
                self.push()
                self.win.show_curtain(self.seats[pid]["name"])
                return
            self.viewer = pid
        self.push()
        if kind == "ai":
            delay = self.win.ai_delay
            if self.game.last is not None and self.game.last is not self._seen_last:
                self._seen_last = self.game.last
                delay = int(delay * 2.2)       # let a resolved exchange sink in
            self.timer.start(delay)

    def reveal(self):
        pend = self.game.pending
        if pend:
            self.last_human = pend[0]
        self.step()
        self.win.show_page("table")

    def _after(self, pid):
        if self.hotseat and self.seats[pid]["kind"] == "human":
            nxt = self.game.pending
            if not nxt or nxt[0] != pid:
                self.viewer = None            # don't leave a hand face-up
        self.step()

    def _ai_move(self):
        pend = self.game.pending
        if not pend or self.seats[pend[0]]["kind"] != "ai":
            return
        pid = pend[0]
        self.game.apply(pid, ai.choose(self.game, pid, self.seats[pid]["level"], self.rng))
        self._after(pid)

    def table_action(self, action: dict):
        pend = self.game.pending
        pid = self.viewer
        if pid is None or not pend or pend[0] != pid or self.seats[pid]["kind"] != "human":
            return
        try:
            self.game.apply(pid, action)
        except GameError as e:
            self.win.status(str(e))
            return
        self._after(pid)

    def remote_action(self, seat: int, action: dict):
        pend = self.game.pending
        if not pend or pend[0] != seat or self.seats[seat]["kind"] != "remote":
            self.host.send(seat, {"t": "error", "msg": "It isn't your move."})
            return
        try:
            self.game.apply(seat, action)
        except GameError as e:
            self.host.send(seat, {"t": "error", "msg": str(e)})
            return
        self._after(seat)

    def remote_left(self, seat: int):
        s = self.seats[seat]
        if s["kind"] != "remote":
            return
        s["kind"], s["level"] = "ai", "normal"
        self.game._say(f"{s['name']} lost the connection — a Normal computer player takes over.")
        self.step()

    def stop(self):
        self.timer.stop()
        if self.host:
            self.host.close()
            self.host = None


class RemoteSession(QtCore.QObject):
    """This screen is a LAN client; the engine runs on the host."""

    def __init__(self, win, client: NetClient):
        super().__init__(win)
        self.win, self.client = win, client
        client.view.connect(self._view)
        client.error.connect(win.status)
        client.lobby.connect(win.show_client_lobby)
        client.closed.connect(self._closed)
        self._done = False

    def _view(self, v: dict):
        self.win.show_table(v)
        self.win.show_page("table")

    def _closed(self, msg: str):
        if self._done:
            return
        self._done = True
        self.win.connection_lost(msg)

    def table_action(self, action: dict):
        self.client.send_action(action)

    def stop(self):
        self._done = True
        self.client.close()


# --------------------------------------------------------------------- setup
class SeatRow(QtWidgets.QWidget):
    removed = QtCore.pyqtSignal(object)

    def __init__(self, name: str, kind: str, level: str, hosting: bool, parent=None):
        super().__init__(parent)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.name = QtWidgets.QLineEdit(name)
        self.name.setMaxLength(24)
        self.kind = QtWidgets.QComboBox()
        self.level = QtWidgets.QComboBox()
        for lv in ai.LEVELS:
            self.level.addItem(LEVEL_NAMES[lv], lv)
        self.level.setCurrentIndex(max(0, self.level.findData(level)))
        rm = QtWidgets.QToolButton()
        rm.setText("✕")
        rm.setToolTip("Remove this seat")
        rm.clicked.connect(lambda: self.removed.emit(self))
        # Never squash a seat: the seat list scrolls instead.
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred,
                           QtWidgets.QSizePolicy.Policy.Fixed)
        lay.addWidget(self.name, 3)
        lay.addWidget(self.kind, 2)
        lay.addWidget(self.level, 1)
        lay.addWidget(rm)
        self.set_hosting(hosting, kind)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self._kind_changed()

    def set_hosting(self, hosting: bool, keep: str | None = None):
        cur = keep or self.kind.currentData()
        self.kind.blockSignals(True)
        self.kind.clear()
        self.kind.addItem("Human, this screen", "human")
        self.kind.addItem("Computer", "ai")
        if hosting:
            self.kind.addItem("LAN player", "remote")
        if cur == "remote" and not hosting:
            cur = "ai"
        self.kind.setCurrentIndex(max(0, self.kind.findData(cur)))
        self.kind.blockSignals(False)
        self._kind_changed()

    def _kind_changed(self):
        k = self.kind.currentData()
        self.level.setVisible(k == "ai")
        self.name.setEnabled(k != "remote")
        if k == "remote":
            self.name.setPlaceholderText("(they choose their name)")

    def data(self) -> dict:
        return {"name": self.name.text().strip(), "kind": self.kind.currentData(),
                "level": self.level.currentData()}


class SeatScroll(QtWidgets.QScrollArea):
    """Asks for room for every seat; the dialog's layout may still give it
    less (down to its minimum), and then it scrolls."""
    def sizeHint(self):
        return QtCore.QSize(super().sizeHint().width(), self.maximumHeight())


class SetupDialog(QtWidgets.QDialog):
    def __init__(self, parent, settings: QtCore.QSettings, deck_path: str):
        super().__init__(parent)
        self.setWindowTitle("New ADSR game")
        self.setStyleSheet(DIALOG_STYLE)
        self.settings = settings
        self.resize(620, 520)
        lay = QtWidgets.QVBoxLayout(self)

        mode_box = QtWidgets.QGroupBox("How would you like to play?")
        ml = QtWidgets.QVBoxLayout(mode_box)
        self.m_local = QtWidgets.QRadioButton(
            "On this computer — against the computer and/or hot-seat (pass the screen)")
        self.m_host = QtWidgets.QRadioButton("Host a LAN game — others join from their own computers")
        self.m_join = QtWidgets.QRadioButton("Join a LAN game hosted elsewhere")
        for r in (self.m_local, self.m_host, self.m_join):
            ml.addWidget(r)
        lay.addWidget(mode_box)

        self.seat_box = QtWidgets.QGroupBox("Seats (play goes in this order; a random seat starts)")
        sl = QtWidgets.QVBoxLayout(self.seat_box)
        rows_host = QtWidgets.QWidget()
        self.rows_lay = QtWidgets.QVBoxLayout(rows_host)
        self.rows_lay.setContentsMargins(0, 0, 4, 0)
        self.rows_lay.addStretch(1)
        self.seat_scroll = SeatScroll()
        self.seat_scroll.setWidget(rows_host)
        self.seat_scroll.setWidgetResizable(True)
        self.seat_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.seat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.seat_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget "
                                       "{ background: transparent; }")
        sl.addWidget(self.seat_scroll, 1)
        add = QtWidgets.QPushButton("Add a seat")
        add.clicked.connect(lambda: self._add_row(f"Player {len(self.rows) + 1}", "ai", "normal"))
        sl.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self.seat_box)
        self.rows: list[SeatRow] = []

        self.host_box = QtWidgets.QGroupBox("Hosting")
        hl = QtWidgets.QFormLayout(self.host_box)
        self.port = QtWidgets.QSpinBox()
        self.port.setRange(1024, 65535)
        self.port.setValue(int(settings.value("port", DEFAULT_PORT)))
        hl.addRow("Port:", self.port)
        hl.addRow("", QtWidgets.QLabel("Players join at: " + ", ".join(local_addresses())))
        lay.addWidget(self.host_box)

        self.join_box = QtWidgets.QGroupBox("Joining")
        jl = QtWidgets.QFormLayout(self.join_box)
        self.j_host = QtWidgets.QLineEdit(str(settings.value("join_host", "")))
        self.j_host.setPlaceholderText("host's address, e.g. 192.168.2.254")
        self.j_port = QtWidgets.QSpinBox()
        self.j_port.setRange(1024, 65535)
        self.j_port.setValue(int(settings.value("join_port", DEFAULT_PORT)))
        self.j_name = QtWidgets.QLineEdit(str(settings.value("join_name", "")))
        self.j_name.setMaxLength(24)
        jl.addRow("Host:", self.j_host)
        jl.addRow("Port:", self.j_port)
        jl.addRow("Your name:", self.j_name)
        lay.addWidget(self.join_box)

        self.deck_box = QtWidgets.QGroupBox("Deck")
        dl = QtWidgets.QVBoxLayout(self.deck_box)
        drow = QtWidgets.QHBoxLayout()
        self.deck = QtWidgets.QLineEdit(deck_path)
        browse = QtWidgets.QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        default = QtWidgets.QPushButton("Default")
        default.clicked.connect(lambda: self.deck.setText(DEFAULT_DECK))
        drow.addWidget(self.deck, 1)
        drow.addWidget(browse)
        drow.addWidget(default)
        dl.addLayout(drow)
        self.deck_info = QtWidgets.QLabel()
        self.deck_info.setWordWrap(True)
        self.deck_info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.deck_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # A long description (20 Kinds and every rule) scrolls in a small box
        # instead of pushing the seats around.
        self.deck_scroll = QtWidgets.QScrollArea()
        self.deck_scroll.setWidget(self.deck_info)
        self.deck_scroll.setWidgetResizable(True)
        self.deck_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.deck_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.deck_scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget "
                                       "{ background: transparent; }")
        self.deck_info.ensurePolished()             # the dialog style sets the font
        lines = QtGui.QFontMetrics(self.deck_info.font()).lineSpacing()
        self.deck_scroll.setFixedHeight(3 * lines + 2)   # three whole lines
        dl.addWidget(self.deck_scroll)
        lay.addWidget(self.deck_box)
        self.deck.textChanged.connect(self._deck_changed)

        lay.addStretch(1)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                        QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        bb.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("Start")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

        mode = str(settings.value("mode", "local"))
        {"local": self.m_local, "host": self.m_host, "join": self.m_join}.get(
            mode, self.m_local).setChecked(True)
        try:
            seats = json.loads(str(settings.value("seats", "")))
        except ValueError:
            seats = None
        if not isinstance(seats, list) or not seats:
            seats = [{"name": "Player 1", "kind": "human", "level": "normal"},
                     {"name": "Ada", "kind": "ai", "level": "normal"},
                     {"name": "Bix", "kind": "ai", "level": "hard"}]
        for s in seats:
            if isinstance(s, dict):
                self._add_row(str(s.get("name", "")), str(s.get("kind", "ai")),
                              str(s.get("level", "normal")))
        for r in (self.m_local, self.m_host, self.m_join):
            r.toggled.connect(self._mode_changed)
        self._mode_changed()
        self._deck_changed()
        self.result: dict | None = None
        self._grow()

    def _floor(self):
        """Qt undercounts the styled group boxes' padding and the wrapped deck
        text, so set the smallest height by hand: everything at its natural
        height except the seat list, which keeps three seats in view."""
        boxes = [b for b in (self.findChildren(QtWidgets.QGroupBox)) if b.isVisibleTo(self)]
        lay = self.layout()
        h = lay.contentsMargins().top() + lay.contentsMargins().bottom()
        for b in boxes:
            bh = b.sizeHint().height()
            if b is self.seat_box:
                bh -= self.seat_scroll.sizeHint().height() - self.seat_scroll.minimumHeight()
            h += bh + lay.spacing()
        h += 50                                      # Start / Cancel
        self.setMinimumHeight(h)

    def _grow(self):
        """Grow (never shrink) to show every seat, as far as the screen allows."""
        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        room = screen.availableGeometry().height() - 80 if screen else 700
        self._floor()
        want = min(self.sizeHint().height(), room)
        if want > self.height():
            self.resize(self.width(), want)

    def mode(self) -> str:
        return "host" if self.m_host.isChecked() else "join" if self.m_join.isChecked() else "local"

    def _add_row(self, name, kind, level):
        if len(self.rows) >= 6:
            return
        row = SeatRow(name, kind, level, self.mode() == "host")
        row.removed.connect(self._remove_row)
        self.rows.append(row)
        self.rows_lay.insertWidget(len(self.rows) - 1, row)   # above the stretch
        self._fit_seats()

    def _remove_row(self, row):
        if len(self.rows) <= 2:
            return
        self.rows.remove(row)
        row.deleteLater()
        self._fit_seats()

    def _fit_seats(self):
        """Show every seat when there's room; below that the list scrolls,
        but at least three seats stay in view."""
        if not self.rows:
            return
        self.rows[0].ensurePolished()               # measure with the dialog's style
        for w in self.rows[0].findChildren(QtWidgets.QWidget):
            w.ensurePolished()
        h = self.rows[0].sizeHint().height()
        gap = self.rows_lay.spacing()
        full = len(self.rows) * (h + gap)
        self.seat_scroll.setMinimumHeight(min(full, 3 * (h + gap)))
        self.seat_scroll.setMaximumHeight(full)
        self.seat_scroll.ensureWidgetVisible(self.rows[-1])
        self.seat_scroll.updateGeometry()
        if hasattr(self, "result"):                 # adding seats after opening
            QtCore.QTimer.singleShot(0, self._grow)

    def _mode_changed(self):
        m = self.mode()
        self.seat_box.setVisible(m != "join")
        self.deck_box.setVisible(m != "join")
        self.host_box.setVisible(m == "host")
        self.join_box.setVisible(m == "join")
        for r in self.rows:
            r.set_hosting(m == "host")
        if hasattr(self, "result"):
            QtCore.QTimer.singleShot(0, self._grow)

    def _browse(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose a deck file", os.path.dirname(self.deck.text() or DEFAULT_DECK),
            "ADSR deck (*.json);;All files (*)")
        if path:
            self.deck.setText(path)

    def _deck_changed(self):
        try:
            cfg = load_config(self.deck.text().strip() or None)
            self.deck_info.setText(deck_summary(cfg))
            self.deck_info.setStyleSheet("")
        except ConfigError as e:
            self.deck_info.setText(f"⚠ {e}")
            self.deck_info.setStyleSheet("color: #d2533f;")
        if hasattr(self, "result"):                 # deck text length changed
            QtCore.QTimer.singleShot(0, self._grow)

    def _ok(self):
        m = self.mode()
        s = self.settings
        s.setValue("mode", m)
        if m == "join":
            host = self.j_host.text().strip()
            name = self.j_name.text().strip()
            if not host or not name:
                QtWidgets.QMessageBox.warning(self, "ADSR", "Enter the host's address and your name.")
                return
            s.setValue("join_host", host)
            s.setValue("join_port", self.j_port.value())
            s.setValue("join_name", name)
            self.result = {"mode": m, "host": host, "port": self.j_port.value(), "name": name}
            self.accept()
            return
        try:
            cfg = load_config(self.deck.text().strip() or None)
        except ConfigError as e:
            QtWidgets.QMessageBox.warning(self, "ADSR", f"The deck file has a problem:\n{e}")
            return
        seats = [r.data() for r in self.rows]
        if not 2 <= len(seats) <= cfg.max_players:
            QtWidgets.QMessageBox.warning(self, "ADSR", f"Choose 2–{cfg.max_players} seats.")
            return
        if m == "host" and not any(x["kind"] == "remote" for x in seats):
            QtWidgets.QMessageBox.warning(self, "ADSR", "A LAN game needs at least one LAN player seat.")
            return
        used = set()
        for i, x in enumerate(seats):
            if x["kind"] == "remote":
                x["name"] = x["name"] or f"Player {i + 1}"
                continue
            base = x["name"] or (f"Player {i + 1}" if x["kind"] == "human" else f"Computer {i + 1}")
            name, n = base, 2
            while name.lower() in used:
                name, n = f"{base} {n}", n + 1
            used.add(name.lower())
            x["name"] = name
        s.setValue("seats", json.dumps(seats))
        s.setValue("deck", cfg.path)
        s.setValue("port", self.port.value())
        self.result = {"mode": m, "seats": seats, "cfg": cfg, "port": self.port.value()}
        self.accept()


TABLE_STYLE = f"""
            QStackedWidget, QStackedWidget > QWidget {{ background: {FELT}; }}
            QLabel {{ color: {INK}; }}
            QScrollArea#exchScroll, QScrollArea#handScroll {{ background: {FELT_DARK};
                border: 1px solid {FELT_LINE}; border-radius: 8px; }}
            QScrollArea#exchScroll > QWidget > QWidget,
            QScrollArea#handScroll > QWidget > QWidget {{ background: {FELT_DARK}; }}
            QPlainTextEdit#log {{ background: {FELT_DARK}; color: {INK};
                border: 1px solid {FELT_LINE}; border-radius: 8px;
                font-family: monospace; font-size: 12px; padding: 4px; }}
            QPushButton {{ background: #2c5f46; color: {INK}; border: 1px solid {FELT_LINE};
                border-radius: 6px; padding: 4px 14px; font-size: 14px; }}
            QPushButton:hover {{ background: #357153; }}
            QPushButton:disabled {{ color: #6f8a7c; background: #23503b; }}
            QPushButton#primary {{ background: {GOLD}; color: #2a2414; font-weight: bold;
                border: 1px solid #c99a2e; }}
            QPushButton#primary:hover {{ background: #f6cf6e; }}
            QPushButton#primary:disabled {{ background: #6d6a4c; color: #3b3a2c; }}
            QComboBox {{ background: {FELT_DARK}; color: {INK}; border: 1px solid {FELT_LINE};
                border-radius: 4px; padding: 3px 8px; min-height: 24px; }}
            QComboBox QAbstractItemView {{ background: {FELT_DARK}; color: {INK};
                selection-background-color: #357153; }}
            QListWidget {{ background: {FELT_DARK}; color: {INK}; border: 1px solid {FELT_LINE};
                border-radius: 6px; font-size: 14px; padding: 4px; }}
"""

DIALOG_STYLE = TABLE_STYLE.replace("QStackedWidget, QStackedWidget > QWidget", "QDialog") + f"""
            QGroupBox {{ color: {INK}; font-weight: bold; border: 1px solid {FELT_LINE};
                border-radius: 6px; margin-top: 10px; padding: 8px 6px 6px 6px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
            QGroupBox QLabel, QRadioButton {{ color: {INK}; font-weight: normal; }}
            QLineEdit, QSpinBox {{ background: {FELT_DARK}; color: {INK};
                border: 1px solid {FELT_LINE}; border-radius: 4px; padding: 3px 6px; }}
            QLineEdit:disabled {{ color: #6f8a7c; }}
            QToolButton {{ background: #2c5f46; color: {INK}; border: 1px solid {FELT_LINE};
                border-radius: 4px; padding: 2px 6px; }}
            QScrollBar:vertical {{ background: {FELT_DARK}; width: 10px; border-radius: 5px; }}
            QScrollBar::handle:vertical {{ background: {FELT_LINE}; min-height: 24px;
                border-radius: 5px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""


# ---------------------------------------------------------------- main window
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, deck_override: str | None = None):
        super().__init__()
        self.setWindowTitle("ADSR")
        if os.path.isfile(ICON):
            self.setWindowIcon(QtGui.QIcon(ICON))
        self.resize(1240, 860)
        self.settings = QtCore.QSettings("ADSR", "adsr")
        if not self.settings.allKeys():          # carry over settings saved as "ASDR"
            old = QtCore.QSettings("ASDR", "asdr")
            for key in old.allKeys():
                self.settings.setValue(key, old.value(key))
        self.deck_path = deck_override or str(self.settings.value("deck", DEFAULT_DECK))
        if not os.path.isfile(self.deck_path):
            self.deck_path = DEFAULT_DECK
        self.ai_delay = SPEEDS.get(str(self.settings.value("speed", "Normal")), 750)
        self.session = None
        self.lobby_host: NetHost | None = None

        self.stack = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stack)
        self.pages: dict[str, QtWidgets.QWidget] = {}

        self.table = TableWidget()
        self.table.action.connect(self._table_action)
        self.table.newGame.connect(self.new_game)
        self._add_page("welcome", self._welcome_page())
        self._add_page("table", self.table)
        self._add_page("curtain", self._curtain_page())
        self._add_page("lobby", self._lobby_page())
        self._menus()
        self._style()
        self.show_page("welcome")

    # ------------------------------------------------------------- pages
    def _add_page(self, key, w):
        self.pages[key] = w
        self.stack.addWidget(w)

    def show_page(self, key):
        self.stack.setCurrentWidget(self.pages[key])

    def _centre(self, *widgets) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(page)
        lay.addStretch(1)
        for w in widgets:
            lay.addWidget(w, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(1)
        return page

    def _welcome_page(self):
        title = QtWidgets.QLabel("ADSR")
        title.setStyleSheet(f"font-size: 64px; font-weight: bold; color: {GOLD}; letter-spacing: 8px;")
        sub = QtWidgets.QLabel("Attack · Decay · Sustain · Release")
        sub.setStyleSheet(f"font-size: 18px; color: {MUTED};")
        cards = QtWidgets.QWidget()
        cl = QtWidgets.QHBoxLayout(cards)
        kinds = [{"name": "Sine", "color": "#3b7fc4", "glyph": "sine"},
                 {"name": "Square", "color": "#c4473f", "glyph": "square"},
                 {"name": "Saw", "color": "#d08a1e", "glyph": "saw"},
                 {"name": "Triangle", "color": "#3f9a5a", "glyph": "triangle"}]
        for i, (t, val, need, dmg) in enumerate([("A", 70, 1, 6), ("D", 100, 2, 0),
                                                 ("S", 60, 1, 0), ("R", 45, 1, 0)]):
            cl.addWidget(CardWidget({"id": i, "kind": i, "type": t, "value": val,
                                     "need": need, "damage": dmg}, kinds))
        b = QtWidgets.QPushButton("New game…")
        b.setObjectName("primary")
        b.setMinimumSize(200, 44)
        b.clicked.connect(self.new_game)
        r = QtWidgets.QPushButton("How to play")
        r.setMinimumSize(200, 36)
        r.clicked.connect(self.show_rules)
        return self._centre(title, sub, cards, b, r)

    def _curtain_page(self):
        self.curtain_lab = QtWidgets.QLabel()
        self.curtain_lab.setStyleSheet(f"font-size: 30px; color: {INK};")
        self.curtain_lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note = QtWidgets.QLabel("Hands stay hidden until the right player is at the screen.")
        note.setStyleSheet(f"color: {MUTED};")
        self.curtain_btn = QtWidgets.QPushButton()
        self.curtain_btn.setObjectName("primary")
        self.curtain_btn.setMinimumSize(260, 46)
        self.curtain_btn.clicked.connect(lambda: self.session and self.session.reveal())
        return self._centre(self.curtain_lab, note, self.curtain_btn)

    def _lobby_page(self):
        self.lobby_title = QtWidgets.QLabel()
        self.lobby_title.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.lobby_info = QtWidgets.QLabel()
        self.lobby_info.setStyleSheet(f"color: {MUTED}; font-size: 14px;")
        self.lobby_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lobby_list = QtWidgets.QListWidget()
        self.lobby_list.setMinimumSize(440, 200)
        row = QtWidgets.QWidget()
        rl = QtWidgets.QHBoxLayout(row)
        self.lobby_start = QtWidgets.QPushButton("Start the game")
        self.lobby_start.setObjectName("primary")
        self.lobby_start.setMinimumHeight(38)
        self.lobby_start.clicked.connect(self._host_start)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setMinimumHeight(38)
        cancel.clicked.connect(self._cancel)
        rl.addWidget(self.lobby_start)
        rl.addWidget(cancel)
        return self._centre(self.lobby_title, self.lobby_info, self.lobby_list, row)

    # ------------------------------------------------------------- menus
    def _menus(self):
        m = self.menuBar().addMenu("&Game")
        a = m.addAction("&New game…", self.new_game)
        a.setShortcut(QtGui.QKeySequence.StandardKey.New)
        a = m.addAction("&How to play", self.show_rules)
        a.setShortcut(QtGui.QKeySequence("F1"))
        m.addSeparator()
        a = m.addAction("&Quit", self.close)
        a.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        self.deck_menu = self.menuBar().addMenu("&Deck")
        self.deck_menu.aboutToShow.connect(self._fill_deck_menu)
        sp = self.menuBar().addMenu("&Speed")
        grp = QtGui.QActionGroup(self)
        cur = str(self.settings.value("speed", "Normal"))
        for name in SPEEDS:
            act = sp.addAction(f"{name} computer players")
            act.setCheckable(True)
            act.setChecked(name == cur)
            act.triggered.connect(lambda _c, n=name: self._speed(n))
            grp.addAction(act)

    def _fill_deck_menu(self):
        """Rebuilt on every opening so it shows the deck the next game will use
        (the New game dialog can change it) and any newly added files."""
        m = self.deck_menu
        m.clear()
        grp = QtGui.QActionGroup(m)
        cur = os.path.realpath(self.deck_path)
        listed = False
        for name, path in bundled_decks():
            act = m.addAction(name + (" (default)" if path == DEFAULT_DECK else ""))
            act.setCheckable(True)
            act.setChecked(os.path.realpath(path) == cur)
            listed |= act.isChecked()
            act.setStatusTip(path)
            act.triggered.connect(lambda _c, p=path: self._use_deck(p))
            grp.addAction(act)
        if not listed:
            act = m.addAction(os.path.basename(self.deck_path))
            act.setCheckable(True)
            act.setChecked(True)
            grp.addAction(act)
        m.addSeparator()
        m.addAction("&Other deck file…", self._choose_deck)
        m.addAction("&About this deck", lambda: QtWidgets.QMessageBox.information(
            self, "ADSR", self._deck_text(self.deck_path)))

    def _deck_text(self, path: str) -> str:
        try:
            return deck_summary(load_config(path))
        except ConfigError as e:
            return f"The deck file has a problem:\n{e}"

    def _choose_deck(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose a deck file", os.path.dirname(self.deck_path),
            "ADSR deck (*.json);;All files (*)")
        if path:
            self._use_deck(path)

    def _use_deck(self, path: str):
        try:
            cfg = load_config(path)
        except ConfigError as e:
            QtWidgets.QMessageBox.warning(self, "ADSR", f"The deck file has a problem:\n{e}")
            return
        self.deck_path = cfg.path
        self.settings.setValue("deck", cfg.path)
        when = "the next game" if self.session else "new games"
        self.status(f"Deck: {cfg.name} — used for {when} (Game › New game)")

    def _speed(self, name):
        self.ai_delay = SPEEDS[name]
        self.settings.setValue("speed", name)

    def _style(self):
        # Scoped to the stack (not the window) so message boxes and the rules
        # dialog keep normal colours.
        self.menuBar().setStyleSheet(
            f"QMenuBar {{ background: {FELT_DARK}; color: {INK}; }}"
            f"QMenuBar::item:selected {{ background: #357153; }}")
        self.statusBar().setStyleSheet(f"QStatusBar {{ background: {FELT_DARK}; color: {GOLD}; }}")
        self.stack.setStyleSheet(TABLE_STYLE)

    # ----------------------------------------------------------- flow
    def status(self, msg: str):
        self.statusBar().showMessage(msg, 6000)

    def show_table(self, v: dict):
        self.table.set_view(v)
        if self.stack.currentWidget() is not self.pages["curtain"]:
            self.show_page("table")

    def show_curtain(self, name: str):
        self.curtain_lab.setText(f"Pass the screen to <b>{name}</b>")
        self.curtain_btn.setText(f"I'm {name} — show my hand")
        self.show_page("curtain")

    def _table_action(self, action: dict):
        if self.session:
            self.session.table_action(action)

    def _shutdown(self):
        if self.session:
            self.session.stop()
            self.session.deleteLater()
            self.session = None
        if self.lobby_host:
            self.lobby_host.close()
            self.lobby_host.deleteLater()
            self.lobby_host = None
        self.table._key = None

    def _cancel(self):
        self._shutdown()
        self.show_page("welcome")

    def new_game(self):
        live = self.session is not None and (
            not isinstance(self.session, LocalSession) or self.session.game.pending is not None)
        if live and QtWidgets.QMessageBox.question(
                self, "ADSR", "Abandon the game in progress?") != \
                QtWidgets.QMessageBox.StandardButton.Yes:
            return
        dlg = SetupDialog(self, self.settings, self.deck_path)
        if dlg.exec() != QtWidgets.QDialog.DialogCode.Accepted or not dlg.result:
            return
        self._shutdown()
        r = dlg.result
        if r["mode"] == "local":
            self.deck_path = r["cfg"].path
            self._start_local(r["cfg"], r["seats"])
        elif r["mode"] == "host":
            self.deck_path = r["cfg"].path
            self._open_lobby(r["cfg"], r["seats"], r["port"])
        else:
            self._join(r["host"], r["port"], r["name"])

    def _start_local(self, cfg, seats, host=None):
        try:
            self.session = LocalSession(self, cfg, seats, host)
        except GameError as e:
            QtWidgets.QMessageBox.warning(self, "ADSR", str(e))
            return
        self.show_page("table")
        self.session.start()

    # LAN hosting
    def _open_lobby(self, cfg, seats, port):
        remote = [i for i, s in enumerate(seats) if s["kind"] == "remote"]
        host = NetHost(remote, self)
        err = host.listen(port)
        if err:
            QtWidgets.QMessageBox.warning(self, "ADSR", f"Could not listen on port {port}: {err}")
            host.deleteLater()
            return
        self.lobby_host = host
        self._lobby = (cfg, seats, port)
        host.joined.connect(self._lobby_refresh)
        host.left.connect(self._lobby_refresh)
        self.lobby_title.setText("Hosting a LAN game")
        self.lobby_info.setText(
            "Other players choose Game ▸ New game ▸ Join, and enter<br><b>"
            + " or ".join(local_addresses()) + f"</b> &nbsp;port <b>{port}</b>")
        self.lobby_start.setVisible(True)
        self._lobby_refresh()
        self.show_page("lobby")

    def _lobby_lines(self) -> list[str]:
        cfg, seats, _ = self._lobby
        out = []
        for i, s in enumerate(seats):
            if s["kind"] == "remote":
                nm = self.lobby_host.names.get(i)
                out.append(f"{i + 1}. {nm} — joined over the LAN" if nm
                           else f"{i + 1}. LAN seat — waiting for a player…")
            elif s["kind"] == "ai":
                out.append(f"{i + 1}. {s['name']} — computer ({LEVEL_NAMES[s['level']]})")
            else:
                out.append(f"{i + 1}. {s['name']} — at the host's screen")
        return out

    def _lobby_refresh(self, *_):
        if self.lobby_host is None:      # the game has started
            return
        lines = self._lobby_lines()
        self.lobby_list.clear()
        self.lobby_list.addItems(lines)
        self.lobby_start.setEnabled(self.lobby_host.full())
        self.lobby_host.broadcast({"t": "lobby", "seats": lines})

    def _host_start(self):
        cfg, seats, _ = self._lobby
        host = self.lobby_host
        if not host.full():
            return
        host.started = True
        for i, s in enumerate(seats):
            if s["kind"] == "remote":
                s["name"] = host.names[i]
        self.lobby_host = None      # the session owns it now
        self._start_local(cfg, seats, host)

    # LAN joining
    def _join(self, host, port, name):
        client = NetClient(self)
        self.session = RemoteSession(self, client)
        self.lobby_title.setText("Joining a LAN game")
        self.lobby_info.setText(f"Connecting to {host}:{port}…")
        self.lobby_list.clear()
        self.lobby_start.setVisible(False)
        client.welcome.connect(lambda seat: self.lobby_info.setText(
            f"Connected as seat {seat + 1}. Waiting for the host to start…"))
        self.show_page("lobby")
        client.connect_to(host, port, name)

    def show_client_lobby(self, lines: list):
        self.lobby_list.clear()
        self.lobby_list.addItems([str(x) for x in lines])

    def connection_lost(self, msg: str):
        QtWidgets.QMessageBox.information(self, "ADSR", msg)
        self._shutdown()
        self.show_page("welcome")

    def show_rules(self):
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("How to play ADSR")
        dlg.resize(760, 720)
        lay = QtWidgets.QVBoxLayout(dlg)
        tb = QtWidgets.QTextBrowser()
        try:
            with open(RULES, encoding="utf-8") as fh:
                tb.setMarkdown(fh.read())
        except OSError:
            tb.setPlainText("RULES.md is missing.")
        lay.addWidget(tb)
        bb = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        dlg.exec()

    def closeEvent(self, e):
        self._shutdown()
        super().closeEvent(e)


def run(deck: str | None = None) -> int:
    import sys
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName("adsr")
    app.setDesktopFileName("adsr")
    app.setStyle("Fusion")
    if deck:
        try:
            load_config(deck)
        except ConfigError as e:
            print(f"adsr: {e}", file=sys.stderr)
            return 1
    win = MainWindow(deck)
    win.show()
    return app.exec()
