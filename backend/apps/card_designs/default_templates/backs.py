"""The back side every template ships with (SPEC §3.3 Classic back, applied to all six).

Member cards keep the desk QR on the front and put the public check QR on the back
(Q5); programme and event cards already carry the check QR on the front, so their back
holds the holder's role or programme details and the return note instead. A check QR
only prints when the public check is on for that card; otherwise the space stays blank.
"""
from .builders import INK, TEAL, Builder

NOTE = "This card belongs to {{name}}. If found, please return it to {{space}}."


def landscape(domain, width, height, *, accent=TEAL):
    back = (Builder(f"back-{domain}").logo("Symbol", "symbol", 4, 4, 8, 8)
            .text("Eyebrow", "About this card", 14, 6, 44, 3.5, size=6, weight=600, colour=accent, upper=True,
                  tracking=0.8)
            .text("Footer note", NOTE, 4, 16, 54, 14, size=7, colour=INK))
    if domain == "member_cards":
        back.label_value("Certifications", "certifications", 4, 33, 54, label_colour=accent)
        back.qr("verify_qr", width - 22.5, 4, 18.5)
        back.text("QR caption", "Check this card", width - 24, 23.5, 21.5, 3.5, size=6, colour=accent, align="center")
    else:
        back.label_value("Role", "role", 4, 33, 26, label_colour=accent)
        back.label_value("Issued", "issued_on", 31, 33, 27, label_colour=accent)
    back.field("Check link", "verify_url", 4, height - 8.5, width - 8, 4, size=6, weight=500, colour=accent)
    return back.layers


def portrait(domain, width, height, *, accent=TEAL):
    back = (Builder(f"back-portrait-{domain}").logo("Symbol", "symbol", 4, 4, 8, 8)
            .text("Eyebrow", "About this pass", 14, 6, width - 18, 3.5, size=6, weight=600, colour=accent, upper=True,
                  tracking=0.8)
            .text("Footer note", NOTE, 4, 16, width - 8, 16, size=7, colour=INK)
            .label_value("Event", "event", 4, 36, width - 8, label_colour=accent)
            .label_value("Organiser", "organisation", 4, 46, width - 8, label_colour=accent)
            .label_value("Issued", "issued_on", 4, 56, width - 8, label_colour=accent))
    back.field("Check link", "verify_url", 4, height - 9, width - 8, 4, size=6, weight=500, colour=accent)
    return back.layers
