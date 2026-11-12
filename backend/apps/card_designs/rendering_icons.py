"""Icon layers (decision 344(b)): the vendored vector icon, contained and centred in its box, filled with one colour.

Every path string is filled on its own with the even-odd rule, in list order (studio_icons). Mono print mode maps the
colour to black or white like other layers. An unknown key draws nothing rather than failing a card.
"""
from reportlab.lib.colors import HexColor

from .rendering_background import colour_for
from .studio_icons import VIEW_BOX, commands, fit


def draw_icon(canvas, document, layer, box):
    from reportlab.pdfgen.canvas import FILL_EVEN_ODD
    x, y, w, h = box
    parsed = commands(layer.get("icon", ""))
    if not parsed:
        return
    scale, dx, dy = fit(w, h)
    canvas.saveState()
    # Icon space is top-left origin, y down; the box sits at (x, y) with y up.
    canvas.translate(x + dx, y + h - dy)
    canvas.scale(scale, -scale)
    if layer.get("flip_x"):
        canvas.translate(VIEW_BOX, 0)
        canvas.scale(-1, 1)
    canvas.setFillColor(HexColor(colour_for(document, layer["colour"])), alpha=layer.get("opacity", 100) / 100)
    for path_commands in parsed:
        path = canvas.beginPath()
        for op, args in path_commands:
            if op == "M":
                path.moveTo(*args)
            elif op == "L":
                path.lineTo(*args)
            elif op == "C":
                path.curveTo(*args)
            else:
                path.close()
        canvas.drawPath(path, fill=1, stroke=0, fillMode=FILL_EVEN_ODD)
    canvas.restoreState()
