"""Image and photo layers (SPEC sections 3 and 7): original or cut-out, mask, zoom/pan, sticker outline, shadow."""
from reportlab.lib.colors import HexColor

from .rendering_background import draw_image
from .rendering_media import compose, draw_composed, needs_raster
from .studio_geometry import shape_kind

INK = "#142C2A"
PLACEHOLDER = "#D7E9E5"  # teal at ~15 % on cream: ink initials on it pass 4.5:1


def _size_mm(box):
    from reportlab.lib.units import mm
    return box[2] / mm, box[3] / mm


def draw_image_layer(canvas, document, side, index, layer, context, box):
    data = context.assets.get(layer["asset_id"])
    if data and needs_raster(layer):
        width_mm, height_mm = _size_mm(box)
        composed = compose(data, layer, width_mm, height_mm, kind_mask=layer.get("mask", "none"),
                           grey=document.get("mono", False), keep_filter=False)
        if composed:
            draw_composed(canvas, composed, *box)
        return
    draw_image(canvas, data, *box, fit=layer.get("fit", "contain"), grey=document.get("mono", False))


def photo_source(layer, context):
    """(bytes, is_cutout) for the layer's variant: original, cutout (falls back to the original when none is ready),
    or auto (the cut-out only when the holder chose it)."""
    variant = layer.get("variant", "original")
    wanted = variant == "cutout" or (variant == "auto" and getattr(context, "use_cutout", False))
    cutout = getattr(context, "photo_cutout", None)
    if wanted and cutout:
        return cutout, True
    return context.photo, False


def _clip(canvas, shape, x, y, w, h, radius_mm):
    from reportlab.lib.units import mm
    from .rendering_shapes import outline_path
    kind = {"square": "rect", "rounded": "rounded", "circle": "ellipse", "arch": "arch"}[shape]
    radius = radius_mm * mm if radius_mm is not None else min(w, h) * 0.14
    return outline_path(canvas, kind, x, y, w, h, radius)


def draw_photo(canvas, document, side, index, layer, context, box):
    from .rendering_text import draw
    x, y, w, h = box
    shape = layer.get("shape", "rounded")
    data, is_cutout = photo_source(layer, context)
    if data and (is_cutout or needs_raster(layer)):
        width_mm, height_mm = _size_mm(box)
        composed = compose(data, layer, width_mm, height_mm, kind_mask="none" if is_cutout else shape_kind(layer),
                           grey=document.get("mono", False))
        if composed:
            draw_composed(canvas, composed, x, y, w, h)
            return
    canvas.saveState()
    canvas.clipPath(_clip(canvas, shape, x, y, w, h, layer.get("radius_mm")), stroke=0, fill=0)
    from .rendering_extras import filtered_photo
    photo = filtered_photo(data, layer)
    if not draw_image(canvas, photo, x, y, w, h, fit="cover", grey=document.get("mono", False)):
        # A tinted tile, so the photo frame still reads on a cream or white card.
        canvas.setFillColor(HexColor("#E6E6E6" if document.get("mono") else PLACEHOLDER))
        canvas.rect(x, y, w, h, fill=1, stroke=0)
        name = str(context.values.get("name", ""))
        initials = "".join(word[:1] for word in name.split()[:2]).upper() or "·"
        style = {"font_family": "Outfit", "font_weight": 700, "font_size_pt": max(6, min(w, h) / 2.2),
                 "align": "center", "valign": "middle", "line_height": 1.0, "tracking_pt": 0, "shrink_to_fit": True}
        draw(canvas, initials, style, colour="#000000" if document.get("mono") else INK,
             x=x, top=y + h, box_width=w, box_height=h)
    canvas.restoreState()
