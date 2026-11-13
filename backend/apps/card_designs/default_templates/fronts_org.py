"""Seven more looks, ported from the sibling app as looks only (O-B4, parity C2): aurora, kasavu, ribbon,
confetti, midnight, sunrise and the standard portrait. The standard landscape IS Classic, so it is not repeated.

Every look is a native v2 recipe drawn for BOTH themes from its own palette (`PALETTES`), so each light/dark
pair passes the 4.5:1 text contrast check on its own background. QR codes sit on white at 18 mm or more.
"""
from .builders import Builder
from .fronts import H, W, _caption, _code

# key -> theme -> (background, ink, label, accent, accent2); `label` is a caption colour that passes on `background`.
PALETTES = {
    # Aurora wears the brand palette (decision 317a): Maker Teal header, Citron ribbon, Warm Cream body, Deep Ink text.
    "aurora": {"light": ("#FFF4E8", "#142C2A", "#006E63", "#006E63", "#DFFF8F"),
               "dark": ("#142C2A", "#FFF4E8", "#DFFF8F", "#006E63", "#DFFF8F")},
    "kasavu": {"light": ("#FBF3DC", "#3B2A00", "#7A5A00", "#C9A227", "#C9A227"),
               "dark": ("#2B1B0E", "#F7E7B4", "#E6C86A", "#C9A227", "#C9A227")},
    "ribbon": {"light": ("#FFFFFF", "#1F1F2E", "#A31D3B", "#A31D3B", "#F3C3CD"),
               "dark": ("#1F1F2E", "#FFFFFF", "#FFB3C1", "#A31D3B", "#F3C3CD")},
    "confetti": {"light": ("#FFFFFF", "#1B1B3A", "#5A3FD0", "#FF6B6B", "#FFD166"),
                 "dark": ("#1B1B3A", "#FFFFFF", "#C9BBFF", "#FF6B6B", "#FFD166")},
    "midnight": {"light": ("#F5F1E6", "#0B0F1A", "#7A5A00", "#0B0F1A", "#B8922A"),
                 "dark": ("#0B0F1A", "#F5F1E6", "#E0BC4F", "#D4AF37", "#D4AF37")},
    "sunrise": {"light": ("#FFF4E0", "#4A2200", "#9A3F00", "#FF8A3D", "#FFC15E"),
                "dark": ("#3A1A05", "#FFE9C7", "#FFC15E", "#FF8A3D", "#FFC15E")},
    "standard_portrait": {"light": ("#FFF4E8", "#142C2A", "#006E63", "#006E63", "#DFFF8F"),
                          "dark": ("#142C2A", "#FFF4E8", "#DFFF8F", "#006E63", "#DFFF8F")},
}
ON_ACCENT = {"aurora": "#FFF4E8", "kasavu": "#2B1B0E", "ribbon": "#FFFFFF", "confetti": "#1B1B3A",
             "midnight": "#0B0F1A", "sunrise": "#4A2200", "standard_portrait": "#FFF4E8"}


def shape(b, name, kind, x, y, w, h, *, fill=None, stroke=None, mm=0.4, radius=0):
    return b._add("shape", name, x, y, w, h, shape=kind, fill=fill, stroke=stroke, stroke_mm=mm, radius_mm=radius)


def _info(b, x, w, ink, label, *, y=24):
    b.label_value("Number", "number", x, y, w, label_colour=label, value_colour=ink, value_height=3.2)
    b.label_value("Valid until", "valid_until", x, y + 7, w, label_colour=label, value_colour=ink, value_height=3.2)
    b.label_value("Plan", "plan", x, y + 14, w, label_colour=label, value_colour=ink, value_height=3.2)
    return b


def _title(b, text, ink, x=5, w=52, y=4):
    return b.text("Space name", text, x, y, w, 4, size=7, weight=700, colour=ink, upper=True, tracking=0.6)


def aurora(domain, theme):
    bg, ink, label, a1, a2 = PALETTES["aurora"][theme]
    on = ON_ACCENT["aurora"]
    b = Builder("aurora").band("Aurora top", 0, 0, W, 10, a1).band("Aurora ribbon", 0, 10, W, 1.6, a2)
    b.band("Aurora tail", 0, 11.6, 12, 0.9, "#FF7447")  # the short Workshop Orange tail under the ribbon
    _title(b, "{{space}}", on, y=3.2, w=70)
    b.photo(5, 15, 18, 22).field("Name", "name", 26, 15, 32, 7.6, size=11, weight=700, colour=ink)
    _info(b, 26, 32, ink, label, y=24).qr(_code(domain), 63.3, 17, 19)
    return b.layers, bg


def kasavu(domain, theme):
    bg, ink, label, gold, _two = PALETTES["kasavu"][theme]
    b = Builder("kasavu").band("Gold top", 0, 0, W, 3, gold).band("Gold bottom", 0, H - 3, W, 3, gold)
    shape(b, "Frame", "rect", 3, 5, W - 6, H - 10, stroke=gold, mm=0.5)
    _title(b, "{{space}}", label, x=7, w=50, y=8).photo(7, 15, 17, 21, shape="square")
    b.field("Name", "name", 27, 15, 31, 7.6, size=11, weight=700, colour=ink)
    _info(b, 27, 31, ink, label, y=24).qr(_code(domain), 62.5, 15, 19)
    b.text("QR caption", _caption(domain), 61, 35, 22, 3.5, size=6, colour=label, align="center")
    return b.layers, bg


def ribbon(domain, theme):
    bg, ink, label, red, soft = PALETTES["ribbon"][theme]
    b = Builder("ribbon").text("Space name", "{{space}}", 5, 4, 55, 4, size=7, weight=700, colour=label, upper=True,
                               tracking=0.6)
    b.band("Ribbon", 0, 12, W, 11, red).field("Name", "name", 5, 13.4, 55, 8, size=13, weight=700, colour="#FFFFFF")
    b.band("Ribbon tail", 0, 23, 9, 3, soft)
    b.label_value("Number", "number", 5, 29, 26, label_colour=label, value_colour=ink, value_height=3.2)
    b.label_value("Valid until", "valid_until", 33, 29, 27, label_colour=label, value_colour=ink, value_height=3.2)
    b.label_value("Plan", "plan", 5, 40, 55, label_colour=label, value_colour=ink, value_height=3.2)
    b.qr(_code(domain), 63.3, 28, 19)
    return b.layers, bg


def confetti(domain, theme):
    bg, ink, label, pink, gold = PALETTES["confetti"][theme]
    b = Builder("confetti")
    for index, (x, y, d, fill) in enumerate(((3, 3, 4, pink), (10, 7, 2.5, gold), (74, 3, 4.5, gold),
                                             (79, 9, 2.5, pink), (3, 46, 3, gold), (72, 46, 4, pink))):
        shape(b, f"Dot {index + 1}", "ellipse", x, y, d, d, fill=fill)
    _title(b, "{{space}}", label, x=16, w=54, y=5)
    b.photo(5, 14, 18, 22, shape="circle").field("Name", "name", 26, 14, 32, 7.6, size=11, weight=700, colour=ink)
    _info(b, 26, 32, ink, label, y=23).qr(_code(domain), 63.3, 17, 19)
    return b.layers, bg


def midnight(domain, theme):
    bg, ink, label, frame, gold = PALETTES["midnight"][theme]
    b = Builder("midnight")
    shape(b, "Frame", "rect", 2.5, 2.5, W - 5, H - 5, stroke=frame, mm=0.5)
    shape(b, "Inner frame", "rect", 4, 4, W - 8, H - 8, stroke=gold, mm=0.2)
    _title(b, "{{space}}", label, x=8, w=48, y=8)
    b.field("Name", "name", 8, 14, 50, 8.5, size=14, weight=700, colour=ink)
    b.rule("Rule", 8, 24, 50, colour=gold)
    _info(b, 8, 24, ink, label, y=27)
    b.label_value("Member since", "member_since", 34, 27, 24, label_colour=label, value_colour=ink, value_height=3.2)
    b.qr(_code(domain), 60, 16, 19)
    return b.layers, bg


def sunrise(domain, theme):
    bg, ink, label, orange, gold = PALETTES["sunrise"][theme]
    b = Builder("sunrise").band("Horizon", 0, 40, W, 14, orange)
    shape(b, "Sun", "ellipse", 56, 31, 14, 14, fill=gold)
    shape(b, "Small sun", "ellipse", 72, 36, 8, 8, fill=gold)
    _title(b, "{{space}}", label, x=5, w=52, y=4)
    b.photo(5, 10, 17, 21).field("Name", "name", 26, 9, 32, 7.6, size=11, weight=700, colour=ink)
    b.label_value("Number", "number", 26, 18, 30, label_colour=label, value_colour=ink, value_height=3.2)
    b.label_value("Valid until", "valid_until", 26, 26, 30, label_colour=label, value_colour=ink, value_height=3.2)
    b.text("Footer", "{{plan}}", 5, 44, 52, 4, size=8, weight=700, colour=ON_ACCENT["sunrise"])
    b.qr(_code(domain), 63.3, 4, 19)
    return b.layers, bg


def standard_portrait(domain, theme):
    """The standard portrait CR80 (53.98 x 85.6 mm): band, photo, details and the desk QR at the foot."""
    bg, ink, label, teal, _lime = PALETTES["standard_portrait"][theme]
    pw = H
    b = Builder("standard-portrait").band("Header band", 0, 0, pw, 13, teal)
    b.text("Space name", "{{space}}", 4, 4, pw - 8, 5, size=8, weight=700, colour="#FFF4E8", upper=True, tracking=0.5,
           align="center")
    b.photo((pw - 20) / 2, 17, 20, 24).field("Name", "name", 4, 44, pw - 8, 8, size=12, weight=700, colour=ink,
                                             align="center")
    b.label_value("Number", "number", 4, 54, 22, label_colour=label, value_colour=ink, value_height=3.2)
    b.label_value("Valid until", "valid_until", 28, 54, 22, label_colour=label, value_colour=ink, value_height=3.2)
    b.qr(_code(domain), (pw - 19) / 2, 63, 19)
    return b.layers, bg
