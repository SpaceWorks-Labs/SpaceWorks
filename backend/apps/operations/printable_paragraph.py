"""Unicode flowable: cluster wrapping, bidi runs and per-font HarfBuzz shaping."""

import re
import unicodedata

from reportlab.platypus import Flowable

from .printable_fonts import clusters, font_runs
from .printable_text_fonts import shaped_run


def visual_runs(text, family, bold):
    # Python-bidi's legacy algorithm does not implement isolate controls. They
    # have no glyphs; omit them from visual ordering, retaining logical ActualText.
    text = text.translate(dict.fromkeys(range(0x2066, 0x206A)))
    runs = font_runs(text, family, bold)
    if not any(unicodedata.bidirectional(c) in ("R", "AL") for c in text):
        result, offset = [], 0
        for filename, run in runs:
            result.append((offset, filename, run))
            offset += len(run)
        return result
    # Use the Unicode bidi algorithm for run order while preserving logical text
    # inside each run for HarfBuzz. Reversing/reshaping strings loses extraction.
    from bidi.algorithm import (get_empty_storage, get_base_level, get_embedding_levels,
        explicit_embed_and_overrides, resolve_weak_types, resolve_neutral_types,
        resolve_implicit_levels, reorder_resolved_levels)
    storage = get_empty_storage()
    storage["base_level"] = get_base_level(text)
    storage["base_dir"] = ("L", "R")[storage["base_level"]]
    get_embedding_levels(text, storage, False, False)
    for index, character in enumerate(storage["chars"]):
        character["index"] = index
    explicit_embed_and_overrides(storage, False)
    resolve_weak_types(storage, False)
    resolve_neutral_types(storage, False)
    resolve_implicit_levels(storage, False)
    levels = {char["index"]: char["level"] for char in storage["chars"]}
    reorder_resolved_levels(storage, False)
    visual = {char["index"]: index for index, char in enumerate(storage["chars"])}
    ordered, offset = [], 0
    for filename, run in runs:
        current, start, level = "", offset, None
        for char in run:
            next_level = levels.get(offset, level)
            if current and next_level != level:
                ordered.append((min(visual.get(i, i) for i in range(start, offset)), start, filename, current))
                current, start = "", offset
            current += char
            level = next_level
            offset += 1
        if current:
            ordered.append((min(visual.get(i, i) for i in range(start, offset)), start, filename, current))
    return [(start, filename, value) for _, start, filename, value in sorted(ordered)]


class UnicodeParagraph(Flowable):
    def __init__(self, text, style, *, family="sans", bold=False):
        super().__init__()
        self.text = str(text).replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
        self.style, self.family, self.bold = style, family, bold
        self.spaceBefore = style.spaceBefore
        self.spaceAfter = style.spaceAfter

    def _width(self, text):
        return sum(shaped_run(font, run, self.style.fontSize)[2]
                   for font, run in font_runs(text, self.family, self.bold))

    def wrap(self, width, height):
        self.width = width
        self.lines = []
        for paragraph in self.text.split("\n"):
            current = ""
            for token in re.findall(r"\S+|[ \t]+", paragraph):
                candidate = current + token
                if self._width(candidate) <= width:
                    current = candidate
                    continue
                if current.strip():
                    self.lines.append(current.rstrip())
                current = token.lstrip()
                # Long unbroken labels and CJK break only at grapheme boundaries.
                if self._width(current) > width:
                    current = ""
                    for cluster in clusters(token.lstrip()):
                        if current and self._width(current + cluster) > width:
                            self.lines.append(current)
                            current = ""
                        current += cluster
            self.lines.append(current.rstrip())
        self.height = max(1, len(self.lines)) * self.style.leading
        return self.width, self.height

    def split(self, width, height):
        count = int(height // self.style.leading)
        if count < 1 or count >= len(self.lines):
            return []
        return [UnicodeParagraph("\n".join(lines), self.style, family=self.family, bold=self.bold)
                for lines in (self.lines[:count], self.lines[count:])]

    def getPlainText(self):
        return self.text

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(self.style.textColor)
        y = self.height - self.style.fontSize
        for line in self.lines:
            width = self._width(line)
            x = (self.width - width) * {0: 0, 1: 0.5, 2: 1}.get(self.style.alignment, 0)
            logical = ("\ufeff" + line).encode("utf-16-be").hex()
            canvas.addLiteral(f"/Span << /ActualText <{logical}> >> BDC")
            positioned = []
            for offset, filename, run in visual_runs(line, self.family, self.bold):
                font, shaped, advance = shaped_run(filename, run, self.style.fontSize, encode=True)
                positioned.append((offset, x, font, shaped))
                x += advance
            # Paint in logical content order at the computed visual positions.
            # This also helps readers which use ToUnicode but ignore ActualText.
            for _, run_x, font, shaped in sorted(positioned):
                text = canvas.beginText(run_x, y)
                text.setFont(font, self.style.fontSize)
                text.textOut(shaped)
                canvas.drawText(text)
            canvas.addLiteral("EMC")
            y -= self.style.leading
