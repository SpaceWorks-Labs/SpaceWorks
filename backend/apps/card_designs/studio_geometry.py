"""Pure geometry shared by every card output and mirrored by the TS twin (SPEC section 2, 5, 7).

No reportlab and no Pillow here: the plan functions are testable without drawing and the golden fixtures assert on them.
"""
import math

PX_PER_MM = 300 / 25.4  # the working raster for effects is 300 dpi


def place(image_w, image_h, box_w, box_h, fit="cover", zoom=1.0, focal_x=50.0, focal_y=50.0):
    """Where an image lands in a box: (left, top, width, height), same unit as the box, top-left origin.

    `cover` and `contain` use one scale; `stretch` fills the box on both axes. `zoom` multiplies the fitted size.
    The focal point works like CSS `object-position`: offset = (box - image) * focal / 100.
    """
    if image_w <= 0 or image_h <= 0:
        return 0.0, 0.0, box_w, box_h
    if fit == "stretch":
        sx, sy = box_w / image_w, box_h / image_h
    else:
        sx = sy = (max if fit == "cover" else min)(box_w / image_w, box_h / image_h)
    width, height = image_w * sx * zoom, image_h * sy * zoom
    return (box_w - width) * focal_x / 100, (box_h - height) * focal_y / 100, width, height


def mask_radius(mask, width, height, radius_mm):
    """Corner radius (mm) a `rounded` mask uses: the layer's own, else 14% of the shorter side (the old photo look)."""
    return min(radius_mm if radius_mm is not None else min(width, height) * 0.14, width / 2, height / 2)


def arch_radius(width, height):
    """An arch is a rectangle with a semicircular top; when the box is too short for that it becomes a rounded one."""
    return width / 2 if height >= width / 2 else None


def shape_kind(layer):
    """The frame a photo or image layer is masked to: square | rounded | circle | arch (photos use `shape`)."""
    if layer["kind"] == "photo":
        return {"square": "none", "rounded": "rounded", "circle": "circle", "arch": "arch"}.get(layer.get("shape", "rounded"), "rounded")
    return layer.get("mask", "none")


POLYGON_SHAPES = ("triangle", "diamond", "hexagon", "star")


def polygon_points(shape, width, height):
    """Vertices (x, y) of a polygon shape inside its box, top-left origin, rounded to 3 decimals (TS twin: polygonPoints).

    triangle: apex top centre; diamond: the four edge midpoints; hexagon: pointy top; star: five points, inner
    radius 0.5 of the outer, both scaled to the box (an ellipse-shaped star in a non-square box).
    """
    w, h = width, height
    if shape == "triangle":
        points = [(w / 2, 0), (w, h), (0, h)]
    elif shape == "diamond":
        points = [(w / 2, 0), (w, h / 2), (w / 2, h), (0, h / 2)]
    elif shape == "hexagon":
        points = [(w / 2, 0), (w, h / 4), (w, h * 3 / 4), (w / 2, h), (0, h * 3 / 4), (0, h / 4)]
    elif shape == "star":
        points = []
        for index in range(10):
            radius = 1.0 if index % 2 == 0 else 0.5
            angle = math.radians(-90 + index * 36)
            points.append((w / 2 + math.cos(angle) * w / 2 * radius, h / 2 + math.sin(angle) * h / 2 * radius))
    else:
        return []
    return [(round(x, 3), round(y, 3)) for x, y in points]


def gradient_line(spec, width, height):
    """Start and end points (x0, y0, x1, y1) of a linear gradient across a box, CSS angle convention (0deg = up)."""
    angle = math.radians(spec.get("angle_deg", 0))
    dx, dy = math.sin(angle), -math.cos(angle)
    half = (abs(width * dx) + abs(height * dy)) / 2
    cx, cy = width / 2, height / 2
    return cx - dx * half, cy - dy * half, cx + dx * half, cy + dy * half


def radial_circle(spec, width, height):
    """Centre and radius (cx, cy, r) of a radial gradient across a box (radius = radius_pct of the half diagonal)."""
    return (width * spec.get("cx_pct", 50) / 100, height * spec.get("cy_pct", 50) / 100,
            math.hypot(width, height) / 2 * spec.get("radius_pct", 100) / 100)


def shadow_pad_mm(layer):
    """How far effects reach beyond a layer box: outline width plus the shadow offset and blur."""
    reach = (layer.get("outline") or {}).get("width_mm", 0)
    shadow = layer.get("shadow")
    if shadow:
        reach += max(abs(shadow["dx_mm"]), abs(shadow["dy_mm"])) + shadow["blur_mm"] * 1.5
    return round(reach, 2)
