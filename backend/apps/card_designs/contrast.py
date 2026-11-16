"""WCAG text contrast against what lies under a text layer (SPEC §3.2, 4.5:1).

The colour under the text is estimated at the layer's centre: the side background
(a flat colour, the gradient at that point, or an uploaded image's mean colour with
its dim overlay), then every visible shape below the text layer whose box contains
that point, alpha-blended in order. The designer runs the same maths in
`frontend/src/components/card-designer/contrast.ts`; both refuse below 4.5:1.
"""
import math
import re

MINIMUM_RATIO = 4.5
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def to_hex(colour):
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in colour)


def luminance(colour):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(first, second):
    a, b = sorted((luminance(first), luminance(second)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def blend(under, over, alpha):
    return tuple(u * (1 - alpha) + o * alpha for u, o in zip(under, over))


def gradient_t(spec, x, y, width, height):
    """Position 0-100 along a gradient at page point (x, y) mm; radial honours centre and radius."""
    if spec.get("type") == "radial":
        half = (math.hypot(width / 2, height / 2) or 1) * spec.get("radius_pct", 100) / 100
        t = math.hypot(x - width * spec.get("cx_pct", 50) / 100, y - height * spec.get("cy_pct", 50) / 100) / half
    else:
        angle = math.radians(spec.get("angle_deg", 0))
        dx, dy = math.sin(angle), -math.cos(angle)
        span = abs(width * dx) + abs(height * dy) or 1
        t = ((x - width / 2) * dx + (y - height / 2) * dy) / span + 0.5
    return max(0.0, min(1.0, t)) * 100


def overlay_blend(colour, overlay, x, y, width, height):
    """`colour` seen through the side overlay gradient (straight alpha) at the point."""
    if not overlay:
        return colour
    stops = overlay["stops"]
    t = gradient_t(overlay, x, y, width, height)
    previous = stops[0]
    for stop in stops:
        if t <= stop["at"]:
            gap = (stop["at"] - previous["at"]) or 1
            k = (t - previous["at"]) / gap
            over = blend(rgb(previous["colour"]), rgb(stop["colour"]), k)
            alpha = (previous["alpha_pct"] + (stop["alpha_pct"] - previous["alpha_pct"]) * k) / 100
            return blend(colour, over, alpha)
        previous = stop
    return blend(colour, rgb(stops[-1]["colour"]), stops[-1]["alpha_pct"] / 100)


def _gradient_at(background, x, y, width, height):
    stops = sorted(background["stops"], key=lambda stop: stop["at"])
    if background.get("type") == "radial":
        half = math.hypot(width / 2, height / 2) or 1
        half *= background.get("radius_pct", 100) / 100
        t = math.hypot(x - width * background.get("cx_pct", 50) / 100, y - height * background.get("cy_pct", 50) / 100) / half
    else:
        angle = math.radians(background.get("angle_deg", 0))
        # CSS convention: 0deg points up, 90deg points right.
        dx, dy = math.sin(angle), -math.cos(angle)
        span = abs(width * dx) + abs(height * dy) or 1
        t = ((x - width / 2) * dx + (y - height / 2) * dy) / span + 0.5
    t = max(0.0, min(1.0, t)) * 100
    previous = stops[0]
    for stop in stops:
        if t <= stop["at"]:
            gap = (stop["at"] - previous["at"]) or 1
            return blend(rgb(previous["colour"]), rgb(stop["colour"]), (t - previous["at"]) / gap)
        previous = stop
    return rgb(stops[-1]["colour"])


def background_at(background, x, y, width, height, asset_colours=None):
    kind = background.get("kind")
    if kind == "gradient":
        return _gradient_at(background, x, y, width, height)
    if kind == "image":
        base = rgb((asset_colours or {}).get(background.get("asset_id"), "#808080"))
        return blend(base, (0, 0, 0), background.get("dim_pct", 0) / 100)
    return rgb(background.get("colour", "#FFFFFF"))


def colour_under(side, layer_index, asset_colours=None):
    """The estimated colour beneath the centre of `side.layers[layer_index]`."""
    layers = side["layers"]
    layer = layers[layer_index]
    x, y = layer["x_mm"] + layer["w_mm"] / 2, layer["y_mm"] + layer["h_mm"] / 2
    colour = background_at(side["background"], x, y, side["page_width_mm"], side["page_height_mm"], asset_colours)
    colour = overlay_blend(colour, side.get("overlay"), x, y, side["page_width_mm"], side["page_height_mm"])
    for below in layers[:layer_index]:
        if below.get("hidden") or below["kind"] not in ("shape", "band") or not below.get("fill"):
            continue
        if below["kind"] == "shape" and below.get("shape") == "line":
            continue
        if below["x_mm"] <= x <= below["x_mm"] + below["w_mm"] and below["y_mm"] <= y <= below["y_mm"] + below["h_mm"]:
            colour = blend(colour, rgb(below["fill"]), below.get("opacity", 100) / 100)
    return colour


def unreadable_layers(side, asset_colours=None):
    """Names of text layers that fall below 4.5:1 on this side."""
    failing = []
    for index, layer in enumerate(side["layers"]):
        if layer.get("hidden") or layer.get("decorative") or layer["kind"] not in ("text", "data_field", "certificate_id"):
            continue
        under = colour_under(side, index, asset_colours)
        if layer.get("highlight"):  # the bar sits under the text: that is the colour it is read against
            under = blend(under, rgb(layer["highlight"]["colour"]), layer.get("opacity", 100) / 100)
        colours = [layer["colour"], *(span["colour"] for span in layer.get("spans") or [] if span.get("colour"))]
        if any(ratio(blend(under, rgb(colour), layer.get("opacity", 100) / 100), under) < MINIMUM_RATIO
               for colour in colours):
            failing.append(layer.get("name") or layer["id"])
    return failing
