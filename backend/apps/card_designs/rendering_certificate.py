"""Certificate drawers on the shared engine: `signature`, `signature_row` and `seal` (decision 315, SPEC 12.2).

A signature is resolved from `context.signatories[slot]` = `{"name", "title", "image": bytes | None, "approved": bool}`
(built from the frozen issuance snapshot by `apps.events.certificates.shared_render`). The consent rule is
enforced HERE as well as at the approval gate: a signatory that has not approved renders as a placeholder rule, never
the image, name or title. A document compiled from a stored v2 certificate keeps the v2 behaviour exactly (a missing
signatory is an error, text uses the v2 metrics).
"""
import math
from io import BytesIO

from django.utils.translation import gettext
from reportlab.lib.colors import HexColor
from rest_framework.exceptions import ValidationError

from .data_fields import merge
from .rendering_background import colour_for
from .rendering_text import draw, draw_compat, draw_runs, is_compat, runs, string_width, visual

IMAGE, RULE, NAME = 0.56, 0.6, 0.8  # fractions of the signature height: image, rule, name start (= the v2 layout)
RULE_INSET = 0.08
SCALLOPS, STAR_POINTS = 24, 12
INNER_RING, RING_TEXT_RADIUS, RING_TEXT_SIZE, RING_SPAN_DEG, OUTER_RING = 0.62, 0.74, 0.22, 300, 0.97  # of the seal radius


def _text(document, canvas, text, layer, **box):
    (draw_compat if is_compat(document) else draw)(canvas, text, layer, **box)


def _signatory(document, context, slot):
    info = (context.signatories or {}).get(slot)
    if info is None and is_compat(document):
        raise ValidationError({"layout": gettext("Add the signatory for this signature layer.")})
    return info


def _style(layer, **over):
    return {"font_family": layer["font_family"], "font_weight": layer["font_weight"], "font_size_pt": layer["font_size_pt"],
            "align": layer["align"], "uppercase": layer.get("uppercase", False), "tracking_pt": layer.get("tracking_pt", 0),
            "line_height": 1.1, "shrink_to_fit": True, "valign": "top", **over}


def _cell(canvas, document, layer, info, x, y, w, h):
    """One signature in box (x, y, w, h) points: image above the rule, name and title below it."""
    approved = info is not None and info.get("approved", True)
    colour = colour_for(document, layer["colour"])
    rule = layer.get("rule")
    if rule is None and is_compat(document):
        rule = {"colour": layer["colour"], "width_pt": 0.6}
    if approved and layer.get("show_image", True) and info.get("image"):
        from reportlab.lib.utils import ImageReader
        canvas.drawImage(ImageReader(BytesIO(info["image"])), x, y + h * (1 - IMAGE), width=w, height=h * IMAGE,
                         preserveAspectRatio=True, anchor="s", mask="auto")
    if rule is not None:
        canvas.setStrokeColor(HexColor(colour_for(document, rule["colour"])))
        canvas.setLineWidth(rule["width_pt"])
        line_y = y + h * (1 - RULE)
        canvas.line(x + w * RULE_INSET, line_y, x + w - w * RULE_INSET, line_y)
    if not approved:
        return  # placeholder: the rule alone; the name and title are withheld with the image
    top = y + h
    if layer.get("show_name", True):
        _text(document, canvas, info["name"], _style(layer), colour=colour, x=x, top=top - h * (RULE + 0.02),
              box_width=w, box_height=h * (NAME - RULE - 0.02))
    if layer.get("show_title", True) and info.get("title"):
        _text(document, canvas, info["title"], _style(layer, font_weight=400, font_size_pt=max(6, layer["font_size_pt"] * 0.8)),
              colour=colour, x=x, top=top - h * NAME, box_width=w, box_height=h * (1 - NAME))


def draw_signature(canvas, document, side, index, layer, context, box):
    x, y, w, h = box
    _cell(canvas, document, layer, _signatory(document, context, layer["signatory_slot"]), x, y, w, h)


def cells(width, gap, count):
    """Equal cells (offset, width) for `count` signatories across `width` with `gap` between them (same unit as the inputs)."""
    cell = (width - gap * (count - 1)) / count
    return [(position * (cell + gap), cell) for position in range(count)]


def draw_signature_row(canvas, document, side, index, layer, context, box):
    """The present signatories of `slots` share the box in equal cells; an absent slot is skipped and the rest re-spaced."""
    from reportlab.lib.units import mm
    x, y, w, h = box
    present = [(slot, info) for slot in layer["slots"] if (info := (context.signatories or {}).get(slot)) is not None]
    if not present:
        return
    for (offset, cell), (_slot, info) in zip(cells(w, layer["gap_mm"] * mm, len(present)), present):
        _cell(canvas, document, layer, info, x + offset, y, cell, h)


def _polygon(canvas, points, fill, stroke):
    path = canvas.beginPath()
    path.moveTo(*points[0])
    for point in points[1:]:
        path.lineTo(*point)
    path.close()
    canvas.drawPath(path, fill=fill, stroke=stroke)


def _points(style, cx, cy, radius):
    if style == "scallop":
        points = [(cx + radius * (0.93 + 0.07 * math.cos(SCALLOPS * t)) * math.sin(t),
                   cy + radius * (0.93 + 0.07 * math.cos(SCALLOPS * t)) * math.cos(t))
                  for t in (math.tau * k / 480 for k in range(480))]
    elif style == "star":
        points = [(cx + radius * (1.0 if k % 2 == 0 else 0.84) * math.sin(math.pi * k / STAR_POINTS),
                   cy + radius * (1.0 if k % 2 == 0 else 0.84) * math.cos(math.pi * k / STAR_POINTS))
                  for k in range(2 * STAR_POINTS)]
    else:
        return False
    return points


def _ring_text(canvas, layer, text, cx, cy, radius, colour):
    """Latin ring text one glyph at a time, centred on 12 o'clock and running clockwise; shrinks to stay under ~300 degrees."""
    spec = layer["label_style"]
    size = max(5.0, radius * RING_TEXT_SIZE)
    while True:
        glyphs = [(char, string_width(part, font, size)) for char in text for font, part in runs(char, spec["font_family"], spec["font_weight"])]
        spans = [width / radius for _char, width in glyphs]
        if sum(spans) <= math.radians(RING_SPAN_DEG) or size <= 5:
            break
        size -= 0.25
    angle = -sum(spans) / 2
    canvas.setFillColor(HexColor(colour))
    for (char, width), span in zip(glyphs, spans):
        canvas.saveState()
        canvas.translate(cx, cy)
        canvas.rotate(-math.degrees(angle + span / 2))
        for font, part in runs(char, spec["font_family"], spec["font_weight"]):
            draw_runs(canvas, [(font, part)], -width / 2, radius - size * 0.35, size)
        canvas.restoreState()
        angle += span


def draw_seal(canvas, document, side, index, layer, context, box):
    x, y, w, h = box
    cx, cy, radius = x + w / 2, y + h / 2, min(w, h) / 2
    from reportlab.lib.units import mm
    stroke_w = layer["stroke_mm"] * mm
    fill, stroke = layer.get("fill"), layer.get("stroke")
    if fill:
        canvas.setFillColor(HexColor(colour_for(document, fill)))
    if stroke:
        canvas.setStrokeColor(HexColor(colour_for(document, stroke)))
        canvas.setLineWidth(stroke_w)
    flags = {"fill": int(bool(fill)), "stroke": int(bool(stroke) and stroke_w > 0)}
    points = _points(layer["style"], cx, cy, radius - stroke_w / 2)
    if points:
        _polygon(canvas, points, **flags)
    else:
        canvas.circle(cx, cy, radius * OUTER_RING - stroke_w / 2, **flags)
    if stroke:  # the inner keyline that bounds the ring text
        canvas.setLineWidth(stroke_w / 2)
        canvas.circle(cx, cy, radius * INNER_RING, fill=0, stroke=1)
    ring = layer.get("ring_text", "")
    if ring:
        _ring_text(canvas, layer, visual(ring), cx, cy, radius * RING_TEXT_RADIUS, colour_for(document, layer["ring_text_colour"]))
    label = merge(layer.get("label", ""), context.values, allow_sensitive=context.allow_sensitive)
    if label.strip():
        spec = layer["label_style"]
        style = {"font_family": spec["font_family"], "font_weight": spec["font_weight"], "font_size_pt": spec["font_size_pt"],
                 "align": "center", "valign": "middle", "uppercase": False, "tracking_pt": 0, "line_height": 1.1,
                 "shrink_to_fit": True}
        side_len = radius * 1.1
        draw(canvas, label, style, colour=colour_for(document, spec["colour"]), x=cx - side_len / 2, top=cy + side_len * 0.4,
             box_width=side_len, box_height=side_len * 0.8)
