"""Small layer builders for the shipped templates; ids are stable uuid5 values."""
from uuid import NAMESPACE_URL, uuid5

INK, TEAL, CREAM, CITRON, SKY, WHITE, LINE = "#142C2A", "#006E63", "#FFF4E8", "#DFFF8F", "#B5CDFF", "#FFFFFF", "#D5D0C6"


def _id(template, name):
    return str(uuid5(NAMESPACE_URL, f"spaceworks:card-template:{template}:{name}"))


class Builder:
    def __init__(self, template):
        self.template = template
        self.layers = []

    def _add(self, kind, name, x, y, w, h, **extra):
        self.layers.append({"id": _id(self.template, f"{len(self.layers)}:{name}"), "kind": kind, "name": name,
                            "x_mm": x, "y_mm": y, "w_mm": w, "h_mm": h, "rotation": 0, "opacity": 100,
                            "locked": False, "hidden": False, **extra})
        return self

    def text(self, name, text, x, y, w, h, *, size=8, weight=400, colour=INK, align="left", upper=False,
             tracking=0, family="Gilroy", valign="top"):
        return self._add("text", name, x, y, w, h, text=text, font_family=family, font_weight=weight,
                         font_size_pt=size, align=align, valign=valign, colour=colour, uppercase=upper,
                         tracking_pt=tracking, line_height=1.15, shrink_to_fit=True)

    def field(self, name, field, x, y, w, h, *, size=8, weight=600, colour=INK, align="left", family="Gilroy"):
        return self._add("data_field", name, x, y, w, h, field=field, font_family=family, font_weight=weight,
                         font_size_pt=size, align=align, valign="top", colour=colour, uppercase=False,
                         tracking_pt=0, line_height=1.15, shrink_to_fit=True)

    def label_value(self, label, field, x, y, w, *, label_colour=TEAL, value_colour=INK, size=8):
        self.text(f"{label} label", label, x, y, w, 3, size=6, weight=600, colour=label_colour, upper=True,
                  tracking=0.4)
        return self.field(label.title(), field, x, y + 3, w, 4.2, size=size, colour=value_colour)

    def band(self, name, x, y, w, h, fill, radius=0):
        return self._add("band", name, x, y, w, h, fill=fill, radius_mm=radius)

    def rule(self, name, x, y, w, colour=LINE):
        return self._add("shape", name, x, y, w, 0.6, shape="line", fill=None, stroke=colour, stroke_mm=0.3,
                         radius_mm=0)

    def logo(self, name, source, x, y, w, h, tile=False):
        return self._add("logo", name, x, y, w, h, source=source, tile=tile)

    def photo(self, x, y, w, h, shape="rounded"):
        return self._add("photo", "Photo", x, y, w, h, shape=shape)

    def qr(self, kind, x, y, size):
        return self._add(kind, "Desk QR" if kind == "desk_qr" else "Check QR", x, y, size, size)

    def perforation(self, x, y, w, h, orientation="vertical", colour=LINE):
        return self._add("perforation", "Perforation", x, y, w, h, colour=colour, orientation=orientation)


def side(width, height, layers, background):
    return {"page_width_mm": width, "page_height_mm": height, "background": background, "layers": layers}


def colour(value):
    return {"kind": "colour", "colour": value}


def document(stock, width, height, front, back=None, background=CREAM, back_background=None):
    return {"version": 2, "stock": stock, "back_enabled": back is not None, "mono": False,
            "watermark": {"kind": "none", "text": "", "asset_id": None, "opacity_pct": 10, "angle_deg": -30,
                          "colour": TEAL},
            "front": side(width, height, front, colour(background)),
            "back": side(width, height, back or [], colour(back_background or background))}
