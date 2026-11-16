"""A canvas double that records what the renderers draw, in page points, so two render paths can be compared.

Only text, images, lines and rectangles are recorded; every other canvas call is accepted and ignored. Layers in these
tests are unrotated, so transforms do not need tracking.
"""


class _Text:
    def __init__(self, x, y):
        self.x, self.y, self.size, self.parts = x, y, 0.0, []

    def setFont(self, _name, size):
        self.size = size

    def textOut(self, text):
        self.parts.append(text)

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class _Path:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


class Recorder:
    def __init__(self):
        self.ops, self.fill = [], None

    def beginText(self, x, y):
        return _Text(x, y)

    def beginPath(self):
        return _Path()

    def setFillColor(self, colour, alpha=None):
        self.fill = colour.hexval() if hasattr(colour, "hexval") else str(colour)

    def drawText(self, text):
        self.ops.append(("text", text.x, text.y, text.size, "".join(text.parts), self.fill))

    def drawImage(self, image, x, y, width=None, height=None, preserveAspectRatio=False, anchor="c", **_):
        if preserveAspectRatio:
            iw, ih = image.getSize()
            scale = min(width / iw, height / ih)
            drawn_w, drawn_h = iw * scale, ih * scale
            x += (width - drawn_w) / 2
            y += 0 if anchor == "s" else (height - drawn_h) / 2
            width, height = drawn_w, drawn_h
        self.ops.append(("image", x, y, width, height))

    def line(self, x1, y1, x2, y2):
        self.ops.append(("line", x1, y1, x2, y2))

    def rect(self, x, y, width, height, **_):
        self.ops.append(("rect", x, y, width, height))

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def comparable(ops, page_points):
    """Drop the full-page paper rectangle and empty text, join the runs of one line, keep the order."""
    out = []
    for op in ops:
        if op[0] == "rect" and all(abs(a - b) < 0.01 for a, b in zip(op[1:], (0, 0, *page_points))):
            continue
        if op[0] == "text":
            if not op[4]:
                continue
            if out and out[-1][0] == "text" and abs(out[-1][2] - op[2]) < 0.01 and out[-1][3] == op[3]:
                out[-1] = (*out[-1][:4], out[-1][4] + op[4], out[-1][5])
                continue
        out.append(tuple(op))
    return out


def same(first, second, tolerance=0.02):
    """Equal operation lists: strings and kinds exactly, numbers within `tolerance` points."""
    if len(first) != len(second):
        return False
    for left, right in zip(first, second):
        if len(left) != len(right):
            return False
        for a, b in zip(left, right):
            if isinstance(a, float) or isinstance(b, float):
                if abs(a - b) > tolerance:
                    return False
            elif a != b:
                return False
    return True
