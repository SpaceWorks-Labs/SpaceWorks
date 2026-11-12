"""The Space Works card templates (six originals, #128 C-30, plus seven looks added by O-B4 in `fronts_org`), each light or dark, all
ordinary two-sided free-canvas documents: Classic, Bold, Minimal, Community, Student
and Event pass.

Classic is the member-card default and follows the R26 ticket (band, caps-label grid,
perforation, desk-QR stub). Event pass is the event default. Every template passes
the 4.5:1 contrast check in both themes, and QR codes sit on white at 18 mm or more.
"""
from django.utils.translation import gettext
from . import backs, backs_org, fronts, fronts_org
from .builders import CREAM, INK, WHITE, document
from .certificates import CERTIFICATE_BUILDERS, CERTIFICATE_LOOKS
from .studio import BUILDERS as _STUDIO, STUDIO_LOOKS
from .themes import THEMES, apply

# Bump when a shipped fallback layout changes; completed outputs remain immutable.
REVISION = 3

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


def _org_look(key, domain, theme):
    """O-B4: one of the seven added looks; each draws its own palette for the theme (see `fronts_org`)."""
    portrait = key == "standard_portrait"
    front, background = getattr(fronts_org, key)(domain, theme)
    width, height = (H, W) if portrait else (W, H)
    back = (backs_org.portrait if portrait else backs_org.landscape)(key, domain, width, height, theme)
    return document("cr80-portrait" if portrait else "cr80-landscape", width, height, front, back,
                    background=background, back_background=background)


def _look(key):
    return lambda domain="member_cards", theme="light": _org_look(key, domain, theme)


ORG_LOOKS = {"aurora": "Aurora", "kasavu": "Kasavu", "ribbon": "Ribbon", "confetti": "Confetti",
             "midnight": "Midnight", "sunrise": "Sunrise", "standard_portrait": "Standard portrait"}
TEMPLATES = {"classic": classic, "bold": bold, "minimal": minimal, "community": community, "student": student,
             "event_pass": event_pass, **{key: _look(key) for key in ORG_LOOKS}, **_STUDIO}
LABELS = {"classic": "Classic", "bold": "Bold", "minimal": "Minimal", "community": "Community",
          "student": "Student", "event_pass": "Event pass", **ORG_LOOKS, **STUDIO_LOOKS}
DEFAULT_FOR_DOMAIN = {"member_cards": "classic", "id_programme": "community", "event_card": "event_pass",
                      "event_ticket": "event_pass", "staff_cards": "classic"}


def build_certificate(key, theme="light"):
    """A built-in certificate look (decision 315): a version 3 `kind: certificate` document."""
    from rest_framework.exceptions import ValidationError
    if key not in CERTIFICATE_BUILDERS or theme not in THEMES:
        raise ValidationError({"template": gettext("Choose one of the certificate templates, light or dark.")})
    return CERTIFICATE_BUILDERS[key](theme)


def build(key, domain, theme="light"):
    from rest_framework.exceptions import ValidationError
    if key not in TEMPLATES or theme not in THEMES:
        raise ValidationError({"template": gettext("Choose one of the card templates, light or dark.")})
    if domain == "staff_cards":  # O-B4 part 2: a member look re-labelled for staff, with a STAFF band
        from .staff import staff_document
        return staff_document(TEMPLATES[key]("staff_cards", theme), theme)
    return TEMPLATES[key](domain, theme)


def default_document(domain):
    return build(DEFAULT_FOR_DOMAIN[domain], domain)
