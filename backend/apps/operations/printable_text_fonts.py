"""Per-render subset fonts preserve logical cluster text in PDF ToUnicode maps.

ReportLab's stock mixed-fragment shaper uses the first font for the entire word.
Shape each resolved font run instead, retaining HarfBuzz advances and offsets.
"""

from contextvars import ContextVar
from pathlib import Path
from threading import RLock

from .printable_fonts import font_paths

_active = ContextVar("printable_font_scope", default=None)
_lock = RLock()


class FontScope:
    def __init__(self):
        self.fonts = {}

    def __enter__(self):
        _lock.acquire()
        self.token = _active.set(self)
        return self

    def __exit__(self, *exc):
        try:
            for font in self.fonts.values():
                font.unregister()
        finally:
            _active.reset(self.token)
            _lock.release()

    def get(self, filename):
        from reportlab.pdfbase import pdfmetrics
        if filename not in self.fonts:
            font = _new_font(filename)
            pdfmetrics.registerFont(font)
            self.fonts[filename] = font
        return self.fonts[filename]


def _new_font(filename):
    from reportlab.pdfbase.ttfonts import TTFont, SUBSETN

    class ClusterFont(TTFont):
        def __init__(self):
            super().__init__("SW-" + Path(filename).stem, str(font_paths()[filename]),
                             asciiReadable=False, shapable=True)
            # A distinct, stable face avoids aliasing the general printable fonts.
            self.face.name = b"SW-" + self.face.name
            self.logical = {}
            self.codes = {}

        def encode(self, gid, logical, width):
            key = (gid, logical)
            if key not in self.codes:
                code = 0xF0000 + len(self.codes)
                if code > 0xFFFFD:
                    raise ValueError("Printable font subset exceeds its glyph bound.")
                self.codes[key] = code
                self.logical[code] = logical
                self.face.charToGlyph[code] = gid
                self.face.charWidths[code] = width
            return chr(self.codes[key])

        def addObjects(self, doc):
            state = self.state[doc]
            subsets = [list(subset) for subset in state.subsets]
            super().addObjects(doc)
            for index, subset in enumerate(subsets):
                name = (SUBSETN(index) + b"+" + self.face.name + self.face.subfontNameX).decode("pdfdoc")
                cmap = doc.idToObject["toUnicodeCMap:" + name]
                # UTF-16BE handles both supplementary characters and ligatures.
                mappings = [f"<{i:02X}> <{self.logical.get(code, chr(code)).encode('utf-16-be').hex()}>"
                            for i, code in enumerate(subset)]
                cmap.content = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
                    "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n"
                    "/CMapName /SWUnicode def /CMapType 2 def\n1 begincodespacerange\n<00> <FF>\n"
                    "endcodespacerange\n" + f"{len(mappings)} beginbfchar\n" + "\n".join(mappings)
                    + "\nendbfchar\nendcmap CMapName currentdict /CMap defineresource pop end end")

    return ClusterFont()


def shaped_run(filename, text, size, *, encode=False):
    import uharfbuzz as hb
    from reportlab.pdfbase.ttfonts import ShapedStr, ShapeData

    scope = _active.get()
    if scope is None:
        raise RuntimeError("Printable text requires a FontScope.")
    font = scope.get(filename)
    face = font.hbFace
    hbfont = hb.Font(face)
    hb.ot_font_set_funcs(hbfont)
    hbfont.scale = (1000, 1000)
    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    buffer.cluster_level = hb.BufferClusterLevel.MONOTONE_CHARACTERS
    hb.shape(hbfont, buffer)
    infos, positions = buffer.glyph_infos, buffer.glyph_positions
    width = sum(position.x_advance for position in positions) * size / 1000
    if not encode:
        return font.fontName, None, width
    starts = sorted({info.cluster for info in infos} | {len(text)})
    ends = dict(zip(starts, starts[1:]))
    seen, chars, shape = set(), [], []
    for info, position in zip(infos, positions):
        cluster = info.cluster
        logical = text[cluster:ends[cluster]] if cluster not in seen else ""
        seen.add(cluster)
        character = font.encode(info.codepoint, logical, hbfont.get_glyph_h_advance(info.codepoint))
        chars.append(character)
        shape.append(ShapeData(cluster, position.x_advance, position.y_advance,
            position.x_offset, position.y_offset, font.face.charWidths[ord(character)]))
    return font.fontName, ShapedStr("".join(chars), shapeData=shape), width
