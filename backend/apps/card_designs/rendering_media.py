"""Image-ish layers through the effects raster: zoom/pan, flip, masks, sticker outline and drop shadow.

A layer with none of those features keeps the original direct draw path (`rendering_background._image`), so documents
written before the Studio print byte-for-byte as before. A layer with any of them is composed at 300 dpi into one
RGBA image (padded for the outline and shadow) by `compose`, then drawn once, so the PDF, PNG, sheets and the holder's
face view show the same pixels (wallet passes carry no photo, and the public verify page shows the original photo). The sticker outline and shadow rules are specified in CARD-STUDIO-SPEC section 5/7.
"""
from io import BytesIO

from .studio_geometry import POLYGON_SHAPES, PX_PER_MM, arch_radius, mask_radius, place, polygon_points, shadow_pad_mm

MAX_EDGE_PX = 3200
SUPERSAMPLE = 4
OUTLINE_THRESHOLD = 5  # of 255: alpha of the blurred silhouette that counts as "inside the sticker"


def needs_raster(layer):
    """Any Studio image feature sends the layer through `compose`; plain layers keep the direct path."""
    return bool(layer.get("outline") or layer.get("shadow") or layer.get("zoom", 1) != 1
                or layer.get("focal_x_pct", 50) != 50 or layer.get("focal_y_pct", 50) != 50
                or layer.get("flip_x") or layer.get("flip_y") or layer.get("fit") == "stretch"
                or layer.get("mask", "none") != "none" or layer.get("shape") == "arch")


def _mask_image(kind, width_px, height_px, radius_px):
    from PIL import Image, ImageDraw
    big = Image.new("L", (width_px * SUPERSAMPLE, height_px * SUPERSAMPLE), 0)
    draw = ImageDraw.Draw(big)
    box = [0, 0, width_px * SUPERSAMPLE - 1, height_px * SUPERSAMPLE - 1]
    scale = SUPERSAMPLE
    if kind == "ellipse":
        draw.ellipse(box, fill=255)
    elif kind == "circle":
        side = min(width_px, height_px) * scale
        left, top = (big.width - side) // 2, (big.height - side) // 2
        draw.ellipse([left, top, left + side - 1, top + side - 1], fill=255)
    elif kind == "rounded":
        draw.rounded_rectangle(box, radius=radius_px * scale, fill=255)
    elif kind in POLYGON_SHAPES:
        draw.polygon(polygon_points(kind, big.width, big.height), fill=255)
    elif kind == "arch":
        top_radius = arch_radius(width_px, height_px)
        if top_radius is None:
            draw.rounded_rectangle(box, radius=radius_px * scale, fill=255)
        else:
            r = top_radius * scale
            draw.rectangle([0, r, box[2], box[3]], fill=255)
            draw.ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
    else:
        draw.rectangle(box, fill=255)
    return big.resize((width_px, height_px), Image.LANCZOS)


def _filter(image, layer):
    from PIL import ImageOps
    kind = layer.get("filter", "none")
    if kind == "none":
        return image
    alpha = image.getchannel("A")
    grey = ImageOps.autocontrast(image.convert("RGB").convert("L"), cutoff=1)
    tinted = grey.convert("RGB") if kind == "grey" else ImageOps.colorize(
        grey, layer.get("duotone_dark", "#142C2A"), layer.get("duotone_light", "#DFFF8F"))
    result = tinted.convert("RGBA")
    result.putalpha(alpha)
    return result


def sticker(alpha, radius_px):
    """The silhouette grown by `radius_px`: Gaussian blur, then a low threshold (sigma = r / 2.05 puts the 5/255
    contour `r` px out from a straight edge), softened by a sub-pixel blur for an antialiased rim."""
    from PIL import ImageFilter
    if radius_px < 0.5:
        return alpha
    blurred = alpha.filter(ImageFilter.GaussianBlur(radius_px / 2.05))
    grown = blurred.point(lambda value: 255 if value >= OUTLINE_THRESHOLD else 0)
    return grown.filter(ImageFilter.GaussianBlur(0.7))


def _tint(alpha, colour, opacity):
    from PIL import Image
    layer = Image.new("RGBA", alpha.size, colour)
    layer.putalpha(alpha.point(lambda value: round(value * opacity)))
    return layer


def compose(data, layer, width_mm, height_mm, *, kind_mask, grey=False, keep_filter=True):
    """Compose the layer's image into a padded RGBA. Returns (image, pad_mm) or None when the bytes are unreadable."""
    from PIL import Image, ImageFilter
    try:
        with Image.open(BytesIO(data)) as opened:
            image = opened.convert("RGBA")
            image.load()
    except Exception:
        return None
    scale = min(1.0, MAX_EDGE_PX / (max(width_mm, height_mm) * PX_PER_MM))
    ppm = PX_PER_MM * scale
    width_px, height_px = max(1, round(width_mm * ppm)), max(1, round(height_mm * ppm))
    if layer.get("flip_x"):
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
    if layer.get("flip_y"):
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
    if keep_filter:
        image = _filter(image, layer)
    left, top, scaled_w, scaled_h = place(image.width, image.height, width_px, height_px, layer.get("fit", "cover"),
                                          layer.get("zoom", 1), layer.get("focal_x_pct", 50), layer.get("focal_y_pct", 50))
    scaled = image.resize((max(1, round(scaled_w)), max(1, round(scaled_h))), Image.LANCZOS)
    pad_mm = shadow_pad_mm(layer)
    pad = round(pad_mm * ppm)
    canvas = Image.new("RGBA", (width_px + 2 * pad, height_px + 2 * pad), (0, 0, 0, 0))
    frame = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
    frame.paste(scaled, (round(left), round(top)))
    if kind_mask != "none":
        radius = round(mask_radius(kind_mask, width_mm, height_mm, layer.get("radius_mm")) * ppm)
        mask = _mask_image(kind_mask, width_px, height_px, radius)
        frame.putalpha(Image.composite(frame.getchannel("A"), Image.new("L", frame.size, 0), mask))
    silhouette = Image.new("L", canvas.size, 0)
    silhouette.paste(frame.getchannel("A"), (pad, pad))
    shape = silhouette
    outline = layer.get("outline")
    if outline:
        shape = sticker(silhouette, outline["width_mm"] * ppm)
    shadow = layer.get("shadow")
    if shadow:
        offset = (round(shadow["dx_mm"] * ppm), round(shadow["dy_mm"] * ppm))
        blurred = shape.filter(ImageFilter.GaussianBlur(max(0.1, shadow["blur_mm"] * ppm / 2)))
        moved = Image.new("L", canvas.size, 0)
        moved.paste(blurred, offset)
        canvas.alpha_composite(_tint(moved, shadow["colour"], shadow["opacity_pct"] / 100))
    if outline:
        canvas.alpha_composite(_tint(shape, outline["colour"], 1.0))
    canvas.alpha_composite(frame, (pad, pad))
    if grey:
        alpha = canvas.getchannel("A")
        canvas = canvas.convert("LA").convert("RGBA")
        canvas.putalpha(alpha)
    return canvas, pad_mm


def draw_composed(canvas, composed, x, y, w, h):
    """Draw a composed layer: x, y, w, h are the layer box in points; the padding hangs outside it."""
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader
    image, pad_mm = composed
    pad = pad_mm * mm
    canvas.drawImage(ImageReader(image), x - pad, y - pad, width=w + 2 * pad, height=h + 2 * pad, mask="auto")


def blurred_background(data, background, width_mm, height_mm):
    """The page-sized background image with fit/zoom/focal/blur applied; None when the bytes are unreadable."""
    from PIL import Image, ImageFilter
    try:
        with Image.open(BytesIO(data)) as opened:
            image = opened.convert("RGBA")
            image.load()
    except Exception:
        return None
    ppm = PX_PER_MM * min(1.0, MAX_EDGE_PX / (max(width_mm, height_mm) * PX_PER_MM))
    width_px, height_px = max(1, round(width_mm * ppm)), max(1, round(height_mm * ppm))
    left, top, scaled_w, scaled_h = place(image.width, image.height, width_px, height_px, background.get("fit", "cover"),
                                          background.get("zoom", 1), background.get("focal_x_pct", 50),
                                          background.get("focal_y_pct", 50))
    page = Image.new("RGBA", (width_px, height_px), (0, 0, 0, 0))
    page.paste(image.resize((max(1, round(scaled_w)), max(1, round(scaled_h))), Image.LANCZOS),
               (round(left), round(top)))
    if background.get("blur_mm"):
        page = page.filter(ImageFilter.GaussianBlur(background["blur_mm"] * ppm))
    return page


GRID = 128


def _stop_at(stops, t):
    """(r, g, b, a 0-1) along overlay stops at t in 0-100, straight-alpha interpolation."""
    previous = stops[0]
    for stop in stops:
        if t <= stop["at"]:
            gap = (stop["at"] - previous["at"]) or 1
            k = (t - previous["at"]) / gap
            a, b = _rgb(previous["colour"]), _rgb(stop["colour"])
            return (*(a[i] + (b[i] - a[i]) * k for i in range(3)),
                    (previous["alpha_pct"] + (stop["alpha_pct"] - previous["alpha_pct"]) * k) / 100)
        previous = stop
    last = stops[-1]
    return (*_rgb(last["colour"]), last["alpha_pct"] / 100)


def _rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def overlay_image(overlay, width_mm, height_mm):
    """The overlay gradient as an RGBA image: computed on a coarse grid then upsampled (it is smooth by nature)."""
    from PIL import Image

    from .contrast import gradient_t
    scale = GRID / max(width_mm, height_mm)
    gw, gh = max(2, round(width_mm * scale)), max(2, round(height_mm * scale))
    grid = Image.new("RGBA", (gw, gh))
    pixels = []
    for row in range(gh):
        y = (row + 0.5) / gh * height_mm
        for col in range(gw):
            r, g, b, a = _stop_at(overlay["stops"], gradient_t(overlay, (col + 0.5) / gw * width_mm, y, width_mm, height_mm))
            pixels.append((round(r), round(g), round(b), round(a * 255)))
    grid.putdata(pixels)
    ppm = min(PX_PER_MM / 2, MAX_EDGE_PX / max(width_mm, height_mm))
    return grid.resize((max(1, round(width_mm * ppm)), max(1, round(height_mm * ppm))), Image.BICUBIC)


def draw_shape_shadow(canvas, layer, box):
    """A blurred, offset silhouette of a shape layer under it (shape kinds are masks: rect, rounded, circle, ...)."""
    from PIL import Image, ImageFilter
    from reportlab.lib.units import mm
    x, y, w, h = box
    shadow = layer["shadow"]
    width_mm, height_mm = w / mm, h / mm
    ppm = PX_PER_MM * min(1.0, MAX_EDGE_PX / (max(width_mm, height_mm) * PX_PER_MM))
    pad_mm = shadow_pad_mm({"shadow": shadow})
    pad = round(pad_mm * ppm)
    width_px, height_px = max(1, round(width_mm * ppm)), max(1, round(height_mm * ppm))
    kind = layer.get("shape", "rect")
    radius_mm = layer.get("radius_mm", 0) or (3.0 if kind == "rounded" else 0)
    mask = _mask_image("rounded" if radius_mm and kind in ("rect", "rounded") else kind if kind in ("circle", "ellipse", "arch", *POLYGON_SHAPES) else "rect",
                       width_px, height_px, round(radius_mm * ppm))
    silhouette = Image.new("L", (width_px + 2 * pad, height_px + 2 * pad), 0)
    silhouette.paste(mask, (pad, pad))
    blurred = silhouette.filter(ImageFilter.GaussianBlur(max(0.1, shadow["blur_mm"] * ppm / 2)))
    moved = Image.new("L", silhouette.size, 0)
    moved.paste(blurred, (round(shadow["dx_mm"] * ppm), round(shadow["dy_mm"] * ppm)))
    draw_composed(canvas, (_tint(moved, shadow["colour"], shadow["opacity_pct"] / 100), pad_mm), x, y, w, h)
