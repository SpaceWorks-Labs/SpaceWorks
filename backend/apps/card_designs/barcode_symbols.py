"""Barcode symbologies (decision 345(c)): Code 128, Code 39, EAN-13, UPC-A, PDF417, Data Matrix and Aztec.

`encode(symbology, payload)` is the ONE encoder for every output: the PDF/PNG renderer, sheets, the holder's
printed-card face and the designer (which asks `POST card-designs/{pk}/barcode` for the same encoding), so the browser
draws exactly the modules the server prints. `rects(encoded, w, h, text_h)` turns an encoding into bar/module
rectangles in the layer box (top-left origin, the box's unit); the TS twin `barcodeRects` must produce the same.

Code 128 keeps ReportLab's encoder (the bars cards printed before this change); the others use `pystrich`
(Apache-2.0, pure Python). Linear codes: `bars` is a string of modules, "1" = dark, with `quiet` light modules either
side. Matrix codes: `rows` is a list of "0"/"1" strings that already include the symbol's quiet zone.
"""
from django.utils.translation import gettext
from rest_framework.exceptions import ValidationError

LINEAR = ("code128", "code39", "ean13", "upca")
MATRIX = ("pdf417", "datamatrix", "aztec")
SYMBOLOGIES = LINEAR + MATRIX
QUIET = {"code128": (10, 10), "code39": (10, 10), "ean13": (11, 7), "upca": (9, 9)}
MAX_PAYLOAD = 80
# Minimum printed box (mm): (number source, desk source) widths and a height; None = this source is refused.
MINIMUM_MM = {"code128": ((30.0, 75.0), 6.0), "code39": ((40.0, None), 8.0), "ean13": ((30.0, None), 10.0),
              "upca": ((30.0, None), 10.0), "pdf417": ((30.0, 45.0), 8.0), "datamatrix": ((10.0, 12.0), 10.0),
              "aztec": ((10.0, 12.0), 10.0)}


def _digits(payload, lengths):
    value = str(payload).strip()
    return value if value.isdigit() and len(value) in lengths else None


def _ean_bars(digits12):
    from pystrich.ean13 import EAN13Encoder
    code = EAN13Encoder(digits12)
    return "101" + code.left_bars + "01010" + code.right_bars + "101", code.full_code


def _code128_bars(payload):
    from reportlab.graphics.barcode.code128 import Code128
    code = Code128(payload, barWidth=1, quiet=False)
    _ = code.width  # validates, encodes and decomposes the value
    widths = {"a": 1, "b": 2, "c": 3, "d": 4}
    return "".join(("1" if letter.isupper() else "0") * widths[letter.lower()] for letter in code.decomposed)


def encode(symbology, payload):
    """-> {"symbology", "kind": "linear", "bars", "quiet", "text"} | {"symbology", "kind": "matrix", "rows"}, or None
    when the payload cannot be carried (an EAN-13 needs 12-13 digits, UPC-A 11-12; anything over 80 characters)."""
    if symbology not in SYMBOLOGIES or not payload or len(str(payload)) > MAX_PAYLOAD:
        return None
    payload = str(payload)
    try:
        if symbology == "code128":
            bars, text = _code128_bars(payload), payload
        elif symbology == "code39":
            from pystrich.code39 import Code39Encoder
            bars, text = Code39Encoder(payload.upper()).bars, payload.upper()
        elif symbology in ("ean13", "upca"):
            digits = _digits(payload, (12, 13) if symbology == "ean13" else (11, 12))
            if digits is None:
                return None
            body = digits[:12] if symbology == "ean13" else "0" + digits[:11]
            bars, text = _ean_bars(body)
            if len(digits) == (13 if symbology == "ean13" else 12) and text[-len(digits):] != digits:
                return None  # a check digit was given and it is wrong
            text = text if symbology == "ean13" else text[1:]
        else:
            from pystrich.aztec import AztecEncoder
            from pystrich.datamatrix import DataMatrixEncoder
            from pystrich.pdf417 import PDF417Encoder
            encoder = {"pdf417": PDF417Encoder, "datamatrix": DataMatrixEncoder, "aztec": AztecEncoder}[symbology]
            matrix = encoder(payload).init_renderer().matrix
            return {"symbology": symbology, "kind": "matrix",
                    "rows": ["".join("1" if cell else "0" for cell in row) for row in matrix]}
    except Exception:
        return None
    left, right = QUIET[symbology]
    return {"symbology": symbology, "kind": "linear", "bars": bars, "quiet": [left, right], "text": text}


GAP_MM = 25.4 / 72  # 1 pt: half above the bars, half between the bars and the text line (the original Code 128 look)


def rects(encoded, width, height, text_height=0.0, gap=GAP_MM):
    """Dark rectangles [x, y, w, h] in the box, top-left origin, all in the box's unit (`gap` too). Linear: bars fill
    the width (quiet zones included) and the height above the text line; matrix: square modules, as large as fit,
    centred."""
    out = []
    if encoded["kind"] == "linear":
        bars, (left, right) = encoded["bars"], encoded["quiet"]
        module = width / (len(bars) + left + right)
        bar_h = max(gap / 4, height - text_height - gap)
        start = None
        for index, cell in enumerate(bars + "0"):
            if cell == "1" and start is None:
                start = index
            elif cell != "1" and start is not None:
                out.append([round((left + start) * module, 4), round(gap / 2, 4), round((index - start) * module, 4),
                            round(bar_h, 4)])
                start = None
        return out
    rows = encoded["rows"]
    module = min(width / len(rows[0]), height / len(rows))
    ox, oy = (width - module * len(rows[0])) / 2, (height - module * len(rows)) / 2
    for r, row in enumerate(rows):
        start = None
        for c, cell in enumerate(row + "0"):
            if cell == "1" and start is None:
                start = c
            elif cell != "1" and start is not None:
                out.append([round(ox + start * module, 4), round(oy + r * module, 4), round((c - start) * module, 4),
                            round(module, 4)])
                start = None
    return out


def minimum(symbology, source):
    """(min width, min height) in mm for a barcode layer; raises a typed 400 when the source cannot use it."""
    (number_w, desk_w), min_h = MINIMUM_MM[symbology]
    width = desk_w if source == "desk" else number_w
    if width is None:
        raise ValidationError({"layers": gettext("This barcode type cannot carry the desk code: use Code 128 or a 2D code.")})
    return width, min_h
