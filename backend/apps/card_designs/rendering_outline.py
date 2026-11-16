"""Outline-drawn faces: glyph outlines as vector paths for fonts ReportLab cannot embed.

Gilroy's two free weights are CFF-outline OpenType files. ReportLab embeds TrueType only, and the font EULA
forbids converting the outlines, so the file stays untouched and each glyph's outline is drawn as a filled
vector path (the same thing a rasteriser does). Printed result: crisp at any DPI, no font file embedded.
Advance widths come from `hmtx`; kerning is not applied (the designer preview does not kern either).
"""
from functools import lru_cache

PREFIX = "outline:"


def is_outline_name(name):
    return isinstance(name, str) and name.startswith(PREFIX)


def pseudo_name(family, weight):
    return f"{PREFIX}{family}:{int(weight)}"


@lru_cache(maxsize=8)
def _face(name):
    from fontTools.ttLib import TTFont

    from .fonts import STUDIO_DIR, OUTLINE
    family, weight = name[len(PREFIX):].rsplit(":", 1)
    font = TTFont(str(STUDIO_DIR / OUTLINE[family][int(weight)]))
    return {"font": font, "cmap": font.getBestCmap() or {}, "glyphs": font.getGlyphSet(),
            "hmtx": font["hmtx"], "upm": font["head"].unitsPerEm}


def codes(family, weight):
    return frozenset(_face(pseudo_name(family, weight))["cmap"])


def string_width(text, name, size):
    face = _face(name)
    notdef = face["hmtx"]["space"][0] if "space" in face["hmtx"].metrics else face["upm"] // 2
    total = sum(face["hmtx"][face["cmap"][ord(ch)]][0] if ord(ch) in face["cmap"] else notdef for ch in text)
    return total * size / face["upm"]


def draw_string(canvas, text, name, size, x, y, tracking=0.0, *, fill=1, stroke=0):
    """Fill `text` at baseline (x, y) in points; returns the x after the run (tracking added per glyph)."""
    from fontTools.pens.basePen import BasePen
    from reportlab.pdfgen.canvas import FILL_NON_ZERO
    face = _face(name)
    scale = size / face["upm"]

    class Pen(BasePen):
        def __init__(self, glyphs, path, ox):
            super().__init__(glyphs)
            self.path, self.ox = path, ox

        def _moveTo(self, pt):
            self.path.moveTo(self.ox + pt[0] * scale, y + pt[1] * scale)

        def _lineTo(self, pt):
            self.path.lineTo(self.ox + pt[0] * scale, y + pt[1] * scale)

        def _curveToOne(self, a, b, c):
            self.path.curveTo(self.ox + a[0] * scale, y + a[1] * scale, self.ox + b[0] * scale, y + b[1] * scale,
                              self.ox + c[0] * scale, y + c[1] * scale)

        def _closePath(self):
            self.path.close()

    path = canvas.beginPath()
    cursor = x
    for char in text:
        glyph = face["cmap"].get(ord(char))
        if glyph is None:
            cursor += face["upm"] // 2 * scale + tracking
            continue
        face["glyphs"][glyph].draw(Pen(face["glyphs"], path, cursor))
        cursor += face["hmtx"][glyph][0] * scale + tracking
    canvas.drawPath(path, stroke=stroke, fill=fill, fillMode=FILL_NON_ZERO)
    return cursor
