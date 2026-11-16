"""Three Card Studio looks (decision 314): portrait CR80 cards drawn with the studio features, in the brand palette.

* `studio_lanyard` - dark gradient, huge background lettering, cut-out photo with a white sticker outline, a two-weight
  name (Gilroy Light + ExtraBold), the role on a highlight bar, a script department line, corner logos and a punch slot.
* `studio_spotlight` - a radial spotlight, a round photo ringed in Citron, the name on two lines.
* `studio_arch` - cream card, a Teal arch behind an arch-masked photo, a Citron role pill.

Each draws its own palette for both themes and passes the 4.5:1 text check; decorative lettering is marked
`decorative` and exempt. The photo layers use variant `cutout` (falls back to the original photo when no cut-out is
ready), so every holder gets a sensible card before the background eraser has run.
"""
from .backs_org import portrait as _back
from .builders import Builder, side
from .fronts import H, W
from .fronts_org import PALETTES

INK, TEAL, CREAM, CITRON, ORANGE, WHITE = "#142C2A", "#006E63", "#FFF4E8", "#DFFF8F", "#FF7447", "#FFFFFF"
LIGHT, ULTRA = "Gilroy Light", "Gilroy ExtraBold"
PALETTES.update({
    "studio_lanyard": {"light": (CREAM, INK, TEAL, TEAL, CITRON), "dark": (INK, CREAM, CITRON, TEAL, CITRON)},
    "studio_spotlight": {"light": (CREAM, INK, TEAL, TEAL, CITRON), "dark": (INK, CREAM, CITRON, TEAL, CITRON)},
    "studio_arch": {"light": (CREAM, INK, TEAL, TEAL, CITRON), "dark": (INK, CREAM, CITRON, TEAL, CITRON)},
})
GUIDES = {"bleed_mm": 0, "safe_mm": 3, "margin_mm": 0, "rulers": [],
          "punch_slot": {"shape": "slot", "side": "front", "x_mm": 21, "y_mm": 3, "w_mm": 12, "h_mm": 3}}


def _stops(*colours):
    last = max(len(colours) - 1, 1)
    return [{"colour": colour, "at": round(100 * index / last, 1)} for index, colour in enumerate(colours)]


def _name(b, x, y, w, h, light, strong, size=19):
    """First name in Gilroy Light over the last name in Gilroy ExtraBold: one text layer, two spans."""
    return b._add("text", "Name", x, y, w, h, text="", font_family=ULTRA, font_weight=800, font_size_pt=size,
                  align="left", valign="top", colour=strong, uppercase=True, tracking_pt=0.3, line_height=1.0,
                  shrink_to_fit=True,
                  spans=[{"text": "{{first_name}}\n", "font_family": LIGHT, "font_weight": 300, "colour": light},
                         {"text": "{{last_name}}", "font_family": ULTRA, "font_weight": 800, "colour": strong}])


def _lettering(b, text, colour, y, h, size):
    return b._add("text", "Background lettering", 0, y, W_PORTRAIT, h, text=text, font_family="Bebas Neue",
                  font_weight=400, font_size_pt=size, align="center", valign="middle", colour=colour,
                  uppercase=True, tracking_pt=0, line_height=0.9, shrink_to_fit=True, decorative=True)


W_PORTRAIT = H  # a portrait CR80 is as wide as the landscape card is tall


def _document(key, domain, theme, background, front, *, guides=None):
    _bg, ink, label, _a, _b = PALETTES[key][theme]
    back_colour = background["colour"] if background["kind"] == "colour" else PALETTES[key][theme][0]
    document = {"version": 3, "stock": "cr80-portrait", "back_enabled": True, "mono": False,
                "watermark": {"kind": "none", "text": "", "asset_id": None, "opacity_pct": 10, "angle_deg": -30, "colour": TEAL},
                "front": {**side(W_PORTRAIT, W, front, background)},
                "back": side(W_PORTRAIT, W, _back(key, domain, W_PORTRAIT, W, theme), {"kind": "colour", "colour": back_colour})}
    if guides:
        document["guides"] = guides
    return document


def lanyard(domain, theme):
    dark = theme == "dark"
    ink, soft = (CREAM, "#2F5F59") if dark else (INK, "#E7DCCB")
    sky = [{"colour": "#0E211F", "at": 0}, {"colour": "#0B3B36", "at": 55}, {"colour": INK, "at": 100}] if dark else _stops(CREAM, "#F6E8D2")
    background = {"kind": "gradient", "type": "linear", "angle_deg": 180, "stops": sky}
    b = Builder("studio_lanyard")
    _lettering(b, "{{space}}", soft if dark else "#EBDDC5", 8, 40, 70)
    b.logo("Space logo", "space", 4, 4, 9, 9).logo("Organisation logo", "organisation", W_PORTRAIT - 13, 4, 9, 9)
    b._add("photo", "Photo", 7, 12, 40, 42, shape="rounded", variant="cutout",
           outline={"width_mm": 0.9, "colour": WHITE}, shadow={"dx_mm": 0.4, "dy_mm": 0.9, "blur_mm": 1.6, "colour": "#000000", "opacity_pct": 40})
    _name(b, 5, 55, 44, 15, ink, ink, 17)
    b._add("text", "Role", 5, 70.8, 30, 4.4, text="{{role}}", font_family="Outfit", font_weight=700, font_size_pt=8,
           align="left", valign="middle", colour=INK, uppercase=True, tracking_pt=1, line_height=1.0, shrink_to_fit=True,
           highlight={"colour": CITRON, "pad_x_mm": 1.4, "pad_y_mm": 0.5, "radius_mm": 0.8})
    b._add("text", "Department", 5, 76.4, 44, 4.6, text="{{team}}", font_family="Pacifico", font_weight=400, font_size_pt=11,
           align="left", valign="middle", colour=CITRON if dark else TEAL, line_height=1.0, shrink_to_fit=True)
    layers = b.layers
    doc = _document("studio_lanyard", domain, theme, background, layers, guides=GUIDES)
    doc["front"]["overlay"] = {"type": "linear", "angle_deg": 180, "stops": [
        {"colour": "#000000", "at": 0, "alpha_pct": 0}, {"colour": "#000000", "at": 100, "alpha_pct": 45 if dark else 0}]}
    return doc


def spotlight(domain, theme):
    dark = theme == "dark"
    ink = CREAM if dark else INK
    background = {"kind": "gradient", "type": "radial", "angle_deg": 0, "cx_pct": 50, "cy_pct": 38, "radius_pct": 80,
                  "stops": _stops("#0F6A60", "#0B3B36", INK) if dark else _stops(WHITE, CREAM, "#F2E3C8")}
    b = Builder("studio_spotlight")
    b.logo("Space logo", "space", 4, 4, 9, 9)
    b._add("shape", "Ring", 9, 12, 36, 36, shape="circle", fill=None, stroke=CITRON if dark else TEAL, stroke_mm=1.2, radius_mm=0)
    b._add("photo", "Photo", 11, 14, 32, 32, shape="circle", variant="cutout",
           shadow={"dx_mm": 0, "dy_mm": 1, "blur_mm": 2, "colour": "#000000", "opacity_pct": 30})
    _name(b, 5, 50, 44, 15, ink, ink, 17).layers[-1]["align"] = "center"
    b._add("text", "Role", 8, 67.5, 38, 4.6, text="{{role}}", font_family="Outfit", font_weight=700, font_size_pt=8,
           align="center", valign="middle", colour=INK, uppercase=True, tracking_pt=1, line_height=1.0, shrink_to_fit=True,
           highlight={"colour": CITRON, "pad_x_mm": 1.6, "pad_y_mm": 0.5, "radius_mm": 1.2})
    b._add("text", "Department", 5, 74, 44, 5, text="{{team}}", font_family="Pacifico", font_weight=400, font_size_pt=10,
           align="center", valign="middle", colour=CITRON if dark else TEAL, line_height=1.0, shrink_to_fit=True)
    return _document("studio_spotlight", domain, theme, background, b.layers)


def arch(domain, theme):
    dark = theme == "dark"
    ink = CREAM if dark else INK
    background = {"kind": "colour", "colour": INK if dark else CREAM}
    b = Builder("studio_arch")
    b.logo("Space logo", "space", 4, 4, 8, 8)
    b._add("shape", "Arch", 8, 12, 38, 44, shape="arch", fill=CITRON if dark else TEAL)
    b._add("photo", "Photo", 10.5, 14.5, 33, 41.5, shape="arch", variant="cutout")
    b._add("text", "Name", 5, 57.5, 44, 11, text="{{name}}", font_family="DM Serif Display", font_weight=400, font_size_pt=17,
           align="center", valign="middle", colour=ink, line_height=1.0, shrink_to_fit=True)
    b._add("text", "Role", 12, 70, 30, 4.6, text="{{role}}", font_family="Outfit", font_weight=600, font_size_pt=8,
           align="center", valign="middle", colour=INK, uppercase=True, tracking_pt=1, line_height=1.0, shrink_to_fit=True,
           highlight={"colour": CITRON if not dark else CITRON, "pad_x_mm": 1.6, "pad_y_mm": 0.5, "radius_mm": 2.2})
    b._add("shape", "Tail", 21, 76.5, 12, 0.9, shape="rect", fill=ORANGE)
    return _document("studio_arch", domain, theme, background, b.layers)


STUDIO_LOOKS = {"studio_lanyard": "Studio lanyard", "studio_spotlight": "Studio spotlight", "studio_arch": "Studio arch"}
BUILDERS = {"studio_lanyard": lanyard, "studio_spotlight": spotlight, "studio_arch": arch}
