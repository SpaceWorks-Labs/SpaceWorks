"""Three built-in certificate looks on the shared engine (decision 315, SPEC 12.3), A4 landscape, light and dark.

* `cert_laurel`   - Classic landscape: cream paper, a teal double frame, a centred serif name and seal.
* `cert_ribbon`   - Modern minimal: white paper, an orange ribbon down the left edge, left-aligned type.
* `cert_spotlight`- Hackathon winner: a radial spotlight, huge background lettering, the name in two weights, the kind
  on a Citron highlight bar and a Citron star seal.

All use the brand palette only, print two signatories (slots 1 and 2; Spotlight uses a three-slot row), the verification QR
and the certificate number, keep every text layer at 4.5:1 or better in both themes (teal text becomes Citron on ink,
orange is never used for text), and leave the 10 mm print margin clear. Decorative lettering is marked `decorative`.
"""
from .builders import Builder, side

INK, TEAL, CREAM, CITRON, ORANGE, WHITE = "#142C2A", "#006E63", "#FFF4E8", "#DFFF8F", "#FF7447", "#FFFFFF"
LIGHT_WEIGHT, ULTRA = "Gilroy Light", "Gilroy ExtraBold"
W, H = 297.0, 210.0
GUIDES = {"bleed_mm": 0, "safe_mm": 10, "margin_mm": 10, "punch_slot": None, "rulers": []}
PALETTE = {  # paper, text, accent (readable on paper), frame/decoration, soft lettering
    "light": {"paper": CREAM, "ink": INK, "accent": TEAL, "frame": TEAL, "soft": "#EBDDC5"},
    "dark": {"paper": INK, "ink": CREAM, "accent": CITRON, "frame": CITRON, "soft": "#1F4A45"},
}


def _signature(b, slot, x, y, w, h, tone, family="Outfit"):
    return b._add("signature", f"Signatory {slot}", x, y, w, h, signatory_slot=slot, show_image=True, show_name=True,
                  show_title=True, rule={"colour": tone["ink"], "width_pt": 0.6}, font_family=family, font_weight=600,
                  font_size_pt=11, align="center", colour=tone["ink"], uppercase=False, tracking_pt=0)


def _serial(b, x, y, w, tone, align="right"):
    return b._add("certificate_id", "Certificate number", x, y, w, 5, format="full", font_family="Outfit", font_weight=500,
                  font_size_pt=7, align=align, valign="middle", colour=tone["ink"], uppercase=False, tracking_pt=0.4,
                  line_height=1.0, shrink_to_fit=True)


def _qr(b, x, y):
    return b._add("verify_qr", "Verification QR", x, y, 22, 22)


def _document(front, background):
    return {"version": 3, "kind": "certificate", "stock": "a4-landscape", "back_enabled": False, "mono": False,
            "watermark": {"kind": "none", "text": "", "asset_id": None, "opacity_pct": 10, "angle_deg": -30, "colour": TEAL},
            "guides": GUIDES, "front": side(W, H, front, background), "back": side(W, H, [], background)}


def laurel(theme):
    tone = PALETTE[theme]
    b = Builder("cert_laurel")
    b._add("shape", "Outer frame", 8, 8, W - 16, H - 16, shape="rect", fill=None, stroke=tone["frame"], stroke_mm=1.2, radius_mm=0)
    b._add("shape", "Inner frame", 12, 12, W - 24, H - 24, shape="rect", fill=None, stroke=tone["frame"], stroke_mm=0.35, radius_mm=0)
    b.logo("Space Works symbol", "symbol", W / 2 - 7, 17, 14, 13)
    b.text("Title", "Certificate", 30, 33, W - 60, 20, size=44, weight=400, colour=tone["ink"], align="center", family="DM Serif Display", valign="middle")
    b.text("Kind", "{{kind}}", 30, 55, W - 60, 7, size=13, weight=600, colour=tone["accent"], align="center", upper=True, tracking=3, valign="middle")
    b.text("Presented to", "This certifies that", 30, 67, W - 60, 7, size=13, weight=400, colour=tone["ink"], align="center", valign="middle")
    b.text("Recipient", "{{recipient}}", 30, 76, W - 60, 22, size=40, weight=400, colour=tone["ink"], align="center", family="DM Serif Display", valign="middle")
    b.rule("Name rule", 88, 100, W - 176, colour=tone["frame"])
    b.text("Took part", "took part in", 30, 104, W - 60, 7, size=12, weight=400, colour=tone["ink"], align="center", valign="middle")
    b.text("Event", "{{event}}", 30, 112, W - 60, 12, size=22, weight=700, colour=tone["ink"], align="center", valign="middle")
    b.text("Date", "{{event_date}}", 30, 126, W - 60, 7, size=13, weight=400, colour=tone["ink"], align="center", valign="middle")
    b.text("Achievement", "{{achievement}}", 30, 135, W - 60, 8, size=13, weight=600, colour=tone["accent"], align="center", valign="middle")
    b._add("seal", "Seal", W / 2 - 14, 150, 28, 28, style="scallop", fill=tone["frame"], stroke=tone["paper"], stroke_mm=0.5,
           label="", label_style={"font_family": "Outfit", "font_weight": 700, "font_size_pt": 9, "colour": tone["paper"]},
           ring_text="SPACE WORKS CERTIFIED", ring_text_colour=tone["paper"])
    _signature(b, 1, 40, 158, 70, 30, tone)
    _signature(b, 2, W - 110, 158, 70, 30, tone)
    _qr(b, 16, 176)
    _serial(b, W - 86, 190, 70, tone)
    return _document(b.layers, {"kind": "colour", "colour": tone["paper"]})


def ribbon(theme):
    tone = {**PALETTE[theme], "paper": WHITE if theme == "light" else INK}
    b = Builder("cert_ribbon")
    b._add("band", "Ribbon", 0, 0, 44, H, fill=ORANGE, radius_mm=0)
    b.logo("Space Works symbol", "symbol", 10, 16, 24, 22)
    b._add("seal", "Seal", 6, 150, 32, 32, style="ring", fill=None, stroke=INK, stroke_mm=0.6, label="",
           label_style={"font_family": "Outfit", "font_weight": 700, "font_size_pt": 9, "colour": INK},
           ring_text="SPACE WORKS CERTIFIED", ring_text_colour=INK)
    b.text("Kind", "Certificate - {{kind}}", 62, 30, 215, 8, size=12, weight=600, colour=tone["accent"], upper=True, tracking=3, valign="middle")
    b.text("Recipient", "{{recipient}}", 62, 46, 215, 26, size=46, weight=700, colour=tone["ink"], valign="middle")
    b.rule("Name rule", 62, 76, 60, colour=ORANGE)
    b.text("Reason", "for taking part in", 62, 86, 215, 8, size=14, weight=400, colour=tone["ink"], valign="middle")
    b.text("Event", "{{event}}", 62, 96, 215, 14, size=24, weight=700, colour=tone["ink"], valign="middle")
    b.text("Date", "{{event_date}}", 62, 112, 215, 8, size=14, weight=400, colour=tone["ink"], valign="middle")
    b.text("Achievement", "{{achievement}}", 62, 124, 215, 10, size=14, weight=600, colour=tone["accent"], valign="middle")
    _signature(b, 1, 62, 158, 68, 30, tone)
    _signature(b, 2, 142, 158, 68, 30, tone)
    _qr(b, 252, 160)
    _serial(b, 62, 194, 120, tone, align="left")
    return _document(b.layers, {"kind": "colour", "colour": tone["paper"]})


def spotlight(theme):
    dark = theme == "dark"
    tone = PALETTE[theme]
    stops = ([{"colour": "#0F6A60", "at": 0}, {"colour": "#0B3B36", "at": 55}, {"colour": INK, "at": 100}] if dark else
             [{"colour": WHITE, "at": 0}, {"colour": CREAM, "at": 55}, {"colour": "#F2E3C8", "at": 100}])
    background = {"kind": "gradient", "type": "radial", "angle_deg": 0, "cx_pct": 30, "cy_pct": 40, "radius_pct": 90, "stops": stops}
    b = Builder("cert_spotlight")
    b._add("text", "Background lettering", 0, 30, W, 120, text="{{kind}}", font_family="Bebas Neue", font_weight=400,
           font_size_pt=96, align="center", valign="middle", colour=tone["soft"], uppercase=True, tracking_pt=0,
           line_height=0.9, shrink_to_fit=True, decorative=True)
    b.logo("Space Works symbol", "symbol", 20, 18, 14, 13)
    b._add("text", "Kind", 20, 40, 60, 7, text="{{kind}}", font_family="Outfit", font_weight=700, font_size_pt=11, align="center",
           valign="middle", colour=INK, uppercase=True, tracking_pt=2, line_height=1.0, shrink_to_fit=True,
           highlight={"colour": CITRON, "pad_x_mm": 2, "pad_y_mm": 0.8, "radius_mm": 1})
    b._add("text", "Recipient", 20, 54, 250, 30, text="", font_family=ULTRA, font_weight=800, font_size_pt=50, align="left",
           valign="middle", colour=tone["ink"], uppercase=True, tracking_pt=0.3, line_height=1.0, shrink_to_fit=True,
           spans=[{"text": "{{first_name}} ", "font_family": LIGHT_WEIGHT, "font_weight": 300, "colour": tone["ink"]},
                  {"text": "{{last_name}}", "font_family": ULTRA, "font_weight": 800, "colour": tone["ink"]}])
    b.text("Event", "{{event}}", 20, 90, 200, 12, size=22, weight=700, colour=tone["ink"], valign="middle")
    b.text("Date", "{{event_date}}", 20, 104, 200, 8, size=14, weight=400, colour=tone["ink"], valign="middle")
    b._add("text", "Achievement", 20, 116, 150, 9, text="{{achievement}}", font_family="Outfit", font_weight=600, font_size_pt=14,
           align="left", valign="middle", colour=INK, uppercase=False, tracking_pt=0, line_height=1.0, shrink_to_fit=True,
           highlight={"colour": CITRON, "pad_x_mm": 2, "pad_y_mm": 0.8, "radius_mm": 1})
    b._add("seal", "Seal", 232, 86, 46, 46, style="star", fill=CITRON, stroke=INK, stroke_mm=0.6, label="{{place}}",
           label_style={"font_family": "Outfit", "font_weight": 800, "font_size_pt": 16, "colour": INK},
           ring_text="SPACE WORKS CERTIFIED", ring_text_colour=INK)
    b._add("signature_row", "Signatories", 20, 154, 200, 32, slots=[1, 2, 3], gap_mm=14, show_image=True, show_name=True,
           show_title=True, rule={"colour": tone["ink"], "width_pt": 0.6}, font_family="Outfit", font_weight=600,
           font_size_pt=11, align="center", colour=tone["ink"], uppercase=False, tracking_pt=0)
    _qr(b, 255, 164)
    _serial(b, 20, 192, 150, tone, align="left")
    return _document(b.layers, background)


CERTIFICATE_LOOKS = {"cert_laurel": "Laurel", "cert_ribbon": "Ribbon", "cert_spotlight": "Spotlight"}
CERTIFICATE_BUILDERS = {"cert_laurel": laurel, "cert_ribbon": ribbon, "cert_spotlight": spotlight}
