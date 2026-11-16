"""Rich text: spans with their own face/size/colour, highlight bar, underline, stroke and shadow (SPEC section 5).

`plan()` is pure layout (no canvas): it returns the lines, their parts and the highlight/underline rectangles, in
points relative to the layer box, and is what the golden fixtures assert. `draw()` paints that plan. A text layer
with none of the rich properties keeps the original single-style path in `rendering_text.draw`.
"""
import re

from .data_fields import merge
from .rendering_text import MIN_PT, ONE_LINE_FLOOR, draw_runs, runs, string_width, visual

ASCENT, DESCENT = 0.9, 0.25  # of the line's largest size: the glyph box a highlight bar wraps
RICH_KEYS = ("spans", "stroke", "shadow", "highlight", "underline")


def is_rich(layer):
    return any(layer.get(key) for key in RICH_KEYS)


def resolve(layer, context):
    """The layer's spans after translation, merge tags and uppercase: dicts of text/family/weight/colour/size/tracking."""
    text, spans = layer["text"], layer.get("spans")
    chosen = (layer.get("translations") or {}).get(getattr(context, "locale", "") or "")
    if chosen is not None:
        text, spans = chosen, None
    out = []
    for span in spans or [{"text": text}]:
        value = merge(span["text"], context.values, allow_sensitive=context.allow_sensitive)
        upper = span.get("uppercase")
        if layer.get("uppercase") if upper is None else upper:
            value = value.upper()
        size = span.get("size_pt") or layer["font_size_pt"] * span.get("size_scale", 1)
        tracking = span.get("tracking_pt")
        out.append({"text": value, "family": span.get("font_family") or layer["font_family"],
                    "weight": span.get("font_weight") or layer["font_weight"], "colour": span.get("colour") or layer["colour"],
                    "size": size, "tracking": layer.get("tracking_pt", 0) if tracking is None else tracking})
    return out


def _units(spans):
    """Words (runs of fragments with no space between), spaces and hard breaks, in order."""
    units, current = [], []

    def flush():
        if current:
            units.append(("word", list(current)))
            current.clear()
    for index, span in enumerate(spans):
        for piece in re.split(r"( |\n)", span["text"]):
            if piece == "":
                continue
            if piece == " ":
                flush()
                units.append(("space", [(" ", index)]))
            elif piece == "\n":
                flush()
                units.append(("break", []))
            else:
                current.append((piece, index))
    flush()
    return units


def _part_width(text, span, scale):
    size = span["size"] * scale
    items = runs(visual(text), span["family"], span["weight"])
    return sum(string_width(part, font, size) for font, part in items) + len(text) * span["tracking"]


def _layout(spans, units, scale, box_width):
    lines, line, used = [], [], 0.0

    def close():
        nonlocal line, used
        while line and line[-1][0].strip() == "":
            line.pop()
        lines.append(line)
        line, used = [], 0.0
    for kind, parts in units:
        if kind == "break":
            close()
            continue
        widths = [_part_width(text, spans[index], scale) for text, index in parts]
        total = sum(widths)
        if kind == "space":
            if line:
                line.append((" ", parts[0][1], total))
                used += total
            continue
        if line and used + total > box_width + 0.01:
            close()
        for (text, index), width in zip(parts, widths):
            line.append((text, index, width))
        used += total
    close()
    return lines


def _metrics(lines, spans, scale, line_height):
    rows = []
    for line in lines:
        size = max((spans[index]["size"] * scale for _text, index, _width in line), default=spans[0]["size"] * scale)
        width = sum(part[2] for part in line)
        if line:  # the last glyph's tracking is not part of the visible line
            width -= spans[line[-1][1]]["tracking"]
        rows.append({"size": size, "leading": size * line_height, "width": width})
    return rows


def plan(spans, layer, box_width, box_height):
    """Fit and lay out. Returns {"scale", "lines": [{"baseline", "x", "width", "size", "parts"}], "bars", "rules"}."""
    units = _units(spans)
    size0 = layer["font_size_pt"]
    smallest = min(span["size"] for span in spans) or size0
    floor = min(1.0, max(ONE_LINE_FLOOR, MIN_PT / smallest))
    step, scale, shrink = 0.5 / size0, 1.0, layer.get("shrink_to_fit", True)
    line_height = layer["line_height"]
    while True:
        lines = _layout(spans, units, scale, box_width)
        rows = _metrics(lines, spans, scale, line_height)
        if sum(row["leading"] for row in rows) <= box_height + 0.01 or not shrink or scale <= floor + 1e-6:
            break
        scale = max(floor, scale - step)
    if len(lines) > 1 and shrink and not any(kind == "break" for kind, _parts in units):
        trial = 1.0
        while trial >= floor - 1e-6:
            one = _layout(spans, units, trial, box_width)
            one_rows = _metrics(one, spans, trial, line_height)
            if len(one) == 1 and one_rows[0]["leading"] <= box_height + 0.01 and one_rows[0]["width"] <= box_width + 0.01:
                if trial >= scale:
                    lines, rows, scale = one, one_rows, trial
                break
            trial -= step
    while len(lines) > 1 and sum(row["leading"] for row in rows) > box_height + 0.01:
        lines.pop()
        rows.pop()
    block = sum(row["leading"] for row in rows)
    start = max(0.0, {"top": 0, "middle": (box_height - block) / 2, "bottom": box_height - block}[layer.get("valign", "top")])
    out, bars, rules, cursor = [], [], [], start
    highlight, underline = layer.get("highlight"), layer.get("underline")
    from reportlab.lib.units import mm
    for line, row in zip(lines, rows):
        baseline = cursor + row["size"] * ASCENT
        shift = {"left": 0, "center": (box_width - row["width"]) / 2, "right": box_width - row["width"]}[layer["align"]]
        parts, x = [], shift
        for text, index, width in line:
            parts.append({"text": text, "span": index, "x": x, "width": width})
            x += width
        out.append({"baseline": baseline, "x": shift, "width": row["width"], "size": row["size"], "parts": parts})
        if highlight and line:
            padx, pady = highlight["pad_x_mm"] * mm, highlight["pad_y_mm"] * mm
            bars.append({"x": shift - padx, "y": baseline - row["size"] * ASCENT - pady, "w": row["width"] + 2 * padx,
                         "h": row["size"] * (ASCENT + DESCENT) + 2 * pady, "radius": highlight["radius_mm"] * mm})
        if underline and line:
            rules.append({"x": shift, "y": baseline + underline["offset_pt"], "w": row["width"],
                          "thickness": underline["thickness_pt"]})
        cursor += row["leading"]
    return {"scale": round(scale, 4), "lines": out, "bars": bars, "rules": rules}


def _stamps(shadow):
    """Offsets (pt) and per-stamp alpha for a text shadow: one hard copy, or a 9-sample ring when blurred."""
    from reportlab.lib.units import mm
    dx, dy, blur = shadow["dx_mm"] * mm, -shadow["dy_mm"] * mm, shadow["blur_mm"] * mm
    opacity = shadow["opacity_pct"] / 100
    if blur <= 0:
        return [(dx, dy)], opacity
    import math
    ring = [(dx + math.cos(k * math.pi / 4) * blur / 2, dy + math.sin(k * math.pi / 4) * blur / 2) for k in range(8)]
    return [(dx, dy), *ring], 1 - (1 - opacity) ** (1 / 9)


def draw(canvas, document, layer, context, box, mono_colour=None):
    """Paint a rich text layer into box (x, y, w, h) points, y up."""
    from reportlab.lib.colors import HexColor
    x, y, w, h = box
    spans = resolve(layer, context)
    if not any(span["text"].strip() for span in spans):
        return
    result = plan(spans, layer, w, h)
    top, alpha = y + h, layer.get("opacity", 100) / 100
    mono = mono_colour is not None
    for bar in result["bars"] if not mono else []:
        canvas.setFillColor(HexColor(layer["highlight"]["colour"]), alpha=alpha)
        canvas.roundRect(x + bar["x"], top - bar["y"] - bar["h"], bar["w"], bar["h"], min(bar["radius"], bar["h"] / 2, bar["w"] / 2),
                         fill=1, stroke=0)
    for rule in result["rules"]:
        canvas.setStrokeColor(HexColor(mono_colour or layer["underline"]["colour"]), alpha=alpha)
        canvas.setLineWidth(rule["thickness"])
        canvas.line(x + rule["x"], top - rule["y"], x + rule["x"] + rule["w"], top - rule["y"])
    for line in result["lines"]:
        base = top - line["baseline"]
        for part in line["parts"]:
            span = spans[part["span"]]
            items = runs(visual(part["text"]), span["family"], span["weight"])
            size, left = span["size"] * result["scale"], x + part["x"]
            if layer.get("shadow") and not mono:
                offsets, each = _stamps(layer["shadow"])
                canvas.setFillColor(HexColor(layer["shadow"]["colour"]))
                canvas.setFillAlpha(alpha * each)
                for ox, oy in offsets:
                    draw_runs(canvas, items, left + ox, base + oy, size, span["tracking"])
                canvas.setFillAlpha(alpha)
            if layer.get("stroke") and not mono:
                canvas.setStrokeColor(HexColor(layer["stroke"]["colour"]))
                canvas.setLineWidth(layer["stroke"]["width_pt"] * 2)
                canvas.setLineJoin(1)
                draw_runs(canvas, items, left, base, size, span["tracking"], stroke=True)
            canvas.setFillColor(HexColor(mono_colour or span["colour"]), alpha=alpha)
            draw_runs(canvas, items, left, base, size, span["tracking"])
