"""The six original Space Works card templates (#128 C-30), all ordinary free-canvas
documents: Classic, Bold, Minimal, Community, Student and Event pass.

Classic is the member-card default and follows the R26 ticket (band, caps-label grid,
perforation, desk-QR stub). Event pass is the event default. Every template passes
the 4.5:1 contrast check, and QR codes sit on white at 18 mm or more.
"""
from .builders import CITRON, CREAM, INK, SKY, TEAL, WHITE, Builder, document

W, H = 85.6, 53.98


def classic(domain="member_cards"):
    eyebrow = "Member" if domain == "member_cards" else "{{programme}}"
    front = (Builder("classic").band("Header band", 0, 0, W, 14, TEAL)
             .logo("Space logo", "space", 3, 2.5, 9, 9)
             .text("Space name", "{{space}}", 14, 3, 44, 4, size=7, weight=700, colour=CREAM, upper=True, tracking=0.5)
             .text("Eyebrow", eyebrow, 14, 8, 44, 3.5, size=6, weight=600, colour=CREAM, upper=True, tracking=0.8)
             .photo(3, 17, 18, 22)
             .field("Name", "name", 24, 16.5, 34, 7, size=11, weight=700)
             .label_value("Number", "number", 24, 25, 16).label_value("Valid until", "valid_until", 41, 25, 17)
             .label_value("Plan", "plan", 24, 34, 16).label_value("Member since", "member_since", 41, 34, 17)
             .perforation(59.5, 14, 2, 39.98))
    qr_kind = "desk_qr" if domain == "member_cards" else "verify_qr"
    front.qr(qr_kind, 63.3, 19, 20).text("QR caption", "Show at the desk" if qr_kind == "desk_qr" else "Scan to check",
                                         62, 40.5, 22.6, 3.5, size=6, colour=TEAL, align="center")
    back = (Builder("classic-back").logo("Symbol", "symbol", 4, 4, 8, 8)
            .text("Eyebrow", "About this card", 14, 6, 40, 3.5, size=6, weight=600, colour=TEAL, upper=True, tracking=0.8)
            .text("Footer note", "This card belongs to {{name}}. If found, please return it to {{space}}.",
                  4, 16, 52, 18, size=7)
            .qr("verify_qr", 63, 4, 18.5)
            .field("Check link", "verify_url", 4, 45, 56, 4, size=6, weight=400, colour=TEAL))
    return document("cr80-landscape", W, H, front.layers, back.layers)


def bold(domain="member_cards"):
    front = (Builder("bold").band("Accent strip", 0, 0, 6, H, CITRON)
             .text("Space name", "{{space}}", 10, 4, 48, 4, size=7, weight=700, colour=CITRON, upper=True, tracking=0.6)
             .field("Name", "name", 10, 11, 48, 12, size=14, weight=700, colour=CREAM)
             .label_value("Number", "number", 10, 27, 22, label_colour=CITRON, value_colour=CREAM)
             .label_value("Valid until", "valid_until", 33, 27, 25, label_colour=CITRON, value_colour=CREAM)
             .field("Role", "role", 10, 38, 48, 5, size=8, weight=500, colour=CREAM)
             .qr("desk_qr" if domain == "member_cards" else "verify_qr", 62, 17, 20))
    return document("cr80-landscape", W, H, front.layers, background=INK)


def minimal(domain="member_cards"):
    front = (Builder("minimal").text("Space name", "{{space}}", 5, 5, 50, 4, size=7, weight=600, colour=TEAL, upper=True)
             .field("Name", "name", 5, 13, 52, 9, size=12, weight=700)
             .rule("Rule", 5, 24, 52)
             .label_value("Number", "number", 5, 28, 24).label_value("Valid until", "valid_until", 31, 28, 26)
             .qr("desk_qr" if domain == "member_cards" else "verify_qr", 61, 17, 20))
    return document("cr80-landscape", W, H, front.layers, background=WHITE)


def community(domain="member_cards"):
    front = (Builder("community").band("Accent", 0, 44, W, 9.98, TEAL)
             .photo(5, 6, 20, 24, shape="rounded")
             .text("Space name", "{{space}}", 29, 6, 32, 4, size=7, weight=700, colour=TEAL, upper=True)
             .field("Name", "name", 29, 12, 32, 9, size=11, weight=700)
             .label_value("Number", "number", 29, 23, 16).label_value("Valid until", "valid_until", 46, 23, 15)
             .text("Footer", "{{organisation}}", 5, 46.5, 55, 4, size=7, weight=600, colour=CREAM)
             .qr("verify_qr" if domain != "member_cards" else "desk_qr", 63.3, 6, 18.5))
    return document("cr80-landscape", W, H, front.layers, background=CREAM)


def student(domain="id_programme"):
    front = (Builder("student").band("Header band", 0, 0, W, 12, SKY)
             .text("Programme", "{{programme}}" if domain != "member_cards" else "{{space}}", 5, 3.5, 56, 5,
                   size=8, weight=700, upper=True, tracking=0.4)
             .photo(5, 16, 17, 21, shape="square")
             .field("Name", "name", 25, 16, 34, 8, size=11, weight=700)
             .label_value("ID number", "number", 25, 26, 34)
             .text("Valid label", "Valid until", 5, 40, 30, 3, size=6, weight=600, colour=TEAL, upper=True)
             .field("Valid until", "valid_until", 5, 43.5, 40, 6, size=11, weight=700)
             .qr("verify_qr" if domain != "member_cards" else "desk_qr", 63.3, 16, 18.5))
    return document("cr80-landscape", W, H, front.layers, background=WHITE)


def event_pass(domain="event_card"):
    pw, ph = H, W
    qr_kind = "desk_qr" if domain == "event_ticket" else "verify_qr"
    front = (Builder("event-pass").band("Event band", 0, 0, pw, 17, TEAL)
             .text("Event name", "{{event}}", 4, 3, pw - 8, 11, size=9, weight=700, colour=CREAM, valign="middle")
             .photo(4, 21, 14, 17, shape="rounded")
             .field("Name", "name", 21, 21, pw - 25, 9, size=10, weight=700)
             .field("Role", "role", 21, 31, pw - 25, 5, size=7, weight=600, colour=TEAL)
             .label_value("Team", "team", 4, 41, 22).label_value("Track", "track", 28, 41, 22)
             .qr(qr_kind, (pw - 22) / 2, 54, 22)
             .text("Caption", "Show this at the door", 4, 78, pw - 8, 4, size=6, colour=TEAL, align="center"))
    return document("cr80-portrait", pw, ph, front.layers, background=WHITE)


TEMPLATES = {"classic": classic, "bold": bold, "minimal": minimal, "community": community, "student": student,
             "event_pass": event_pass}
LABELS = {"classic": "Classic", "bold": "Bold", "minimal": "Minimal", "community": "Community",
          "student": "Student", "event_pass": "Event pass"}
DEFAULT_FOR_DOMAIN = {"member_cards": "classic", "id_programme": "community", "event_card": "event_pass",
                      "event_ticket": "event_pass"}


def build(key, domain):
    from rest_framework.exceptions import ValidationError
    if key not in TEMPLATES:
        raise ValidationError({"template": "Choose one of the six templates."})
    return TEMPLATES[key](domain)


def default_document(domain):
    return build(DEFAULT_FOR_DOMAIN[domain], domain)
