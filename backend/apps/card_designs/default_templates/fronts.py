"""The front side of each of the six original templates (#128 C-30), drawn light.

Name boxes hold two lines, so a long name wraps at a readable size instead of shrinking
to the 6 pt floor, and value boxes are one line (shrink to 60 %, then an ellipsis); QR codes sit on white at 18 mm
or more, and everything readable stays inside the 3 mm safe area.
"""
from .builders import CITRON, CREAM, INK, SKY, TEAL, WHITE, Builder

W, H = 85.6, 53.98


def _code(domain):
    return "desk_qr" if domain in ("member_cards", "event_ticket") else "verify_qr"


def _caption(domain):
    return {"member_cards": "Show at the desk", "event_ticket": "Show at the door"}.get(domain, "Scan to check")


def classic(domain):
    eyebrow = "Member" if domain == "member_cards" else "{{programme}}"
    return (Builder("classic").band("Header band", 0, 0, W, 14, TEAL)
            .logo("Space logo", "space", 3.5, 2.5, 9, 9, tile=True)
            .text("Space name", "{{space}}", 15, 3.2, 42, 4, size=7, weight=700, colour=CREAM, upper=True, tracking=0.5)
            .text("Eyebrow", eyebrow, 15, 7.6, 42, 3.5, size=6, weight=600, colour=CREAM, upper=True, tracking=0.8)
            .photo(3.5, 17.5, 18, 22)
            .field("Name", "name", 24, 17, 33.5, 7.6, size=11, weight=700)
            .label_value("Number", "number", 24, 25, 33.5, value_height=3.2)
            .label_value("Valid until", "valid_until", 24, 32, 33.5, value_height=3.2)
            .label_value("Plan", "plan", 24, 39, 16, value_height=3.2)
            .label_value("Member since", "member_since", 41, 39, 16.5, value_height=3.2)
            .text("Footer", "{{organisation}}", 3.5, 46.5, 54, 3.5, size=6, weight=500, colour=TEAL)
            .perforation(59.5, 14, 2, 39.98)
            .qr(_code(domain), 63.3, 18.5, 19)
            .text("QR caption", _caption(domain), 61.8, 39.5, 22, 3.5, size=6, colour=TEAL, align="center")).layers


def bold(domain, *, dark):
    strip, label, value, accent = (CITRON, CITRON, CREAM, CITRON) if dark else (TEAL, TEAL, INK, TEAL)
    return (Builder("bold").band("Accent strip", 0, 0, 6, H, strip)
            .text("Space name", "{{space}}", 10, 4, 48, 4, size=7, weight=700, colour=accent, upper=True, tracking=0.6)
            .field("Name", "name", 10, 11, 49, 7.5, size=15, weight=700, colour=value)
            .field("Role", "role", 10, 19.5, 49, 4.5, size=8, weight=500, colour=value)
            .label_value("Number", "number", 10, 28, 23, label_colour=label, value_colour=value)
            .label_value("Valid until", "valid_until", 34, 28, 25, label_colour=label, value_colour=value)
            .label_value("Plan", "plan", 10, 38, 49, label_colour=label, value_colour=value)
            .qr(_code(domain), 63, 17, 19.5)).layers


def minimal(domain):
    return (Builder("minimal").text("Space name", "{{space}}", 5, 5, 52, 4, size=7, weight=600, colour=TEAL, upper=True,
                                    tracking=0.4)
            .field("Name", "name", 5, 13, 53, 8.5, size=13, weight=700)
            .rule("Rule", 5, 22, 53)
            .label_value("Number", "number", 5, 26, 25).label_value("Valid until", "valid_until", 31, 26, 27)
            .label_value("Plan", "plan", 5, 36, 53)
            .qr(_code(domain), 61.5, 17, 19.5)).layers


def community(domain):
    return (Builder("community").band("Accent", 0, 44, W, 9.98, TEAL)
            .photo(5, 6, 19, 24, shape="rounded")
            .text("Space name", "{{space}}", 28, 6, 31, 4, size=7, weight=700, colour=TEAL, upper=True)
            .field("Name", "name", 28, 11.5, 31, 8.8, size=11, weight=700)
            .label_value("Number", "number", 28, 21, 34, value_height=3.2)
            .label_value("Valid until", "valid_until", 28, 28, 31, value_height=3.2)
            .label_value("Plan", "plan", 28, 35, 31, value_height=3.2)
            .text("Footer", "{{organisation}}", 5, 47, 55, 4, size=7, weight=600, colour=CREAM)
            .qr(_code(domain), 63.6, 6, 18.5)).layers


def student(domain):
    return (Builder("student").band("Header band", 0, 0, W, 12, SKY)
            .text("Programme", "{{programme}}" if domain != "member_cards" else "{{space}}", 5, 3.8, 56, 5,
                  size=8, weight=700, upper=True, tracking=0.4)
            .photo(5, 16, 17, 21, shape="square")
            .field("Name", "name", 25, 16, 35, 7.6, size=11, weight=700)
            .label_value("ID number", "number", 25, 24, 35)
            .label_value("Role", "role", 25, 32, 35)
            .text("Valid label", "Valid until", 5, 40.5, 40, 3, size=6, weight=600, colour=TEAL, upper=True)
            .field("Valid until", "valid_until", 5, 43.8, 55, 5.6, size=11, weight=700)
            .qr(_code(domain), 63.6, 16, 18.5)).layers


def event_pass(domain):
    pw = H
    return (Builder("event-pass").band("Event band", 0, 0, pw, 17, TEAL)
            .text("Event name", "{{event}}", 4, 3, pw - 8, 11, size=9, weight=700, colour=CREAM, valign="middle")
            .photo(4, 21, 14, 17, shape="rounded")
            .field("Name", "name", 21, 21.3, pw - 25, 6.5, size=10, weight=700)
            .field("Role", "role", 21, 28, pw - 25, 4.6, size=7, weight=600, colour=TEAL)
            .field("Number", "number", 21, 33, pw - 25, 4.2, size=7, weight=500)
            .label_value("Team", "team", 4, 41, 22).label_value("Track", "track", 28, 41, 22)
            .qr(_code(domain), (pw - 22) / 2, 54, 22)
            .text("Caption", "Show this at the door", 4, 78.5, pw - 8, 4, size=6, colour=TEAL, align="center")).layers


__all__ = ["CITRON", "WHITE", "classic", "bold", "minimal", "community", "student", "event_pass", "W", "H"]
