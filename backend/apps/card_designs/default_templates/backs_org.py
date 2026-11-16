"""Backs for the seven O-B4 looks: the shared back layout drawn in each look's own palette.

Same content as `backs.landscape` / `backs.portrait` (return note, the public check QR on member cards,
certifications), but ink and caption colours come from the look, so the dark variants stay readable.
"""
from .builders import Builder
from .fronts_org import PALETTES

NOTE = "This card belongs to {{name}}. If found, please return it to {{space}}."


def landscape(key, domain, width, height, theme):
    _bg, ink, label, _a, _b = PALETTES[key][theme]
    back = (Builder(f"back-{key}-{domain}").logo("Symbol", "symbol", 4, 4, 8, 8)
            .text("Eyebrow", "About this card", 14, 6, 44, 3.5, size=6, weight=600, colour=label, upper=True,
                  tracking=0.8)
            .text("Footer note", NOTE, 4, 16, 54, 14, size=7, colour=ink))
    if domain == "member_cards":
        back.label_value("Certifications", "certifications", 4, 33, 54, label_colour=label, value_colour=ink)
        back.qr("verify_qr", width - 22.5, 4, 18.5)
        back.text("QR caption", "Check this card", width - 24, 23.5, 21.5, 3.5, size=6, colour=label, align="center")
    else:
        back.label_value("Role", "role", 4, 33, 26, label_colour=label, value_colour=ink)
        back.label_value("Issued", "issued_on", 31, 33, 27, label_colour=label, value_colour=ink)
    back.field("Check link", "verify_url", 4, height - 8.5, width - 8, 4, size=6, weight=500, colour=label)
    return back.layers


def portrait(key, domain, width, height, theme):
    _bg, ink, label, _a, _b = PALETTES[key][theme]
    back = (Builder(f"back-{key}-portrait-{domain}").logo("Symbol", "symbol", 4, 4, 8, 8)
            .text("Eyebrow", "About this card", 14, 6, width - 18, 3.5, size=6, weight=600, colour=label, upper=True,
                  tracking=0.8)
            .text("Footer note", NOTE, 4, 16, width - 8, 16, size=7, colour=ink)
            .label_value("Certifications", "certifications", 4, 36, width - 8, label_colour=label, value_colour=ink))
    if domain == "member_cards":
        back.qr("verify_qr", (width - 19) / 2, 48, 19)
    back.field("Check link", "verify_url", 4, height - 9, width - 8, 4, size=6, weight=500, colour=label)
    return back.layers
