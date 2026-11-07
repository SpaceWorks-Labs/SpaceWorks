"""The six original Space Works card templates (#128 C-30), each light or dark, all
ordinary two-sided free-canvas documents: Classic, Bold, Minimal, Community, Student
and Event pass.

Classic is the member-card default and follows the R26 ticket (band, caps-label grid,
perforation, desk-QR stub). Event pass is the event default. Every template passes
the 4.5:1 contrast check in both themes, and QR codes sit on white at 18 mm or more.
"""
from django.utils.translation import gettext
from . import backs, fronts
from .builders import CREAM, INK, WHITE, document
from .themes import THEMES, apply

# Bump when a shipped fallback layout changes; completed outputs remain immutable.
REVISION = 2

W, H = fronts.W, fronts.H
_FRONT_BACKGROUND = {"classic": CREAM, "minimal": WHITE, "community": CREAM, "student": WHITE, "event_pass": WHITE}


def _landscape(key, domain, theme):
    if key == "bold":
        # Bold draws its own dark front (ink card, citron accents); the cream back darkens like the rest.
        front, background = fronts.bold(domain, dark=theme == "dark"), INK if theme == "dark" else CREAM
    else:
        front, background = getattr(fronts, key)(domain), _FRONT_BACKGROUND[key]
    doc = document("cr80-landscape", W, H, front, backs.landscape(domain, W, H), background=background,
                   back_background=CREAM)
    return apply(doc, theme)


def _portrait(domain, theme):
    doc = document("cr80-portrait", H, W, fronts.event_pass(domain), backs.portrait(domain, H, W),
                   background=_FRONT_BACKGROUND["event_pass"], back_background=CREAM)
    return apply(doc, theme)


def classic(domain="member_cards", theme="light"):
    return _landscape("classic", domain, theme)


def bold(domain="member_cards", theme="light"):
    return _landscape("bold", domain, theme)


def minimal(domain="member_cards", theme="light"):
    return _landscape("minimal", domain, theme)


def community(domain="member_cards", theme="light"):
    return _landscape("community", domain, theme)


def student(domain="id_programme", theme="light"):
    return _landscape("student", domain, theme)


def event_pass(domain="event_card", theme="light"):
    return _portrait(domain, theme)


TEMPLATES = {"classic": classic, "bold": bold, "minimal": minimal, "community": community, "student": student,
             "event_pass": event_pass}
LABELS = {"classic": "Classic", "bold": "Bold", "minimal": "Minimal", "community": "Community",
          "student": "Student", "event_pass": "Event pass"}
DEFAULT_FOR_DOMAIN = {"member_cards": "classic", "id_programme": "community", "event_card": "event_pass",
                      "event_ticket": "event_pass"}


def build(key, domain, theme="light"):
    from rest_framework.exceptions import ValidationError
    if key not in TEMPLATES or theme not in THEMES:
        raise ValidationError({"template": gettext("Choose one of the six templates, light or dark.")})
    return TEMPLATES[key](domain, theme)


def default_document(domain):
    return build(DEFAULT_FOR_DOMAIN[domain], domain)
