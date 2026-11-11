"""Merge tags a card design may place, and the sample values the designer previews.

Values come from a frozen snapshot assembled at render time by the holder adapter
(`holders.py`); a design never names a model field. `field:<key>` places a programme
or event answer. The two sensitive tags render only when the holder opted in (§3.4).
"""
from django.utils.translation import gettext
import re

from rest_framework.exceptions import ValidationError

TAGS = (
    "name", "number", "plan", "valid_until", "member_since", "role", "title", "team", "track",
    "event", "space", "organisation", "programme", "issued_on", "verify_url", "certifications",
    # E-B1: event badges print the holder's email and crew kind.
    "email", "crew_kind",
    # E-B2 (D17): ticket merge fields.
    "date", "time", "venue", "price", "order",
    # O-B4 part 2: member units (`unit_chain`) and staff ID cards (`holders_staff`).
    "unit", "unit_code", "units", "level1", "level2", "level3", "level4", "roles", "machine_scope",
)
SENSITIVE_TAGS = ("blood_group", "emergency_contact")
ANSWER_PREFIX = "field:"
_ANSWER_KEY = re.compile(r"^[a-z0-9_]{1,40}$")
_TAG = re.compile(r"{{\s*([^{}]*?)\s*}}")

SAMPLE_SHORT = {
    "name": "Priya Raman", "number": "TNK-0042", "plan": "Monthly", "valid_until": "31 Dec 2026",
    "member_since": "Mar 2024", "role": "Member", "title": "Treasurer", "team": "Night Owls",
    "track": "Hardware", "event": "Spring Build Night", "space": "Tinkerspace",
    "organisation": "Makers Guild", "programme": "Student ID", "issued_on": "2 Nov 2026",
    "verify_url": "example.org/verify/c/…", "certifications": "Laser induction", "blood_group": "O+", "emergency_contact": "Arjun · 98765 43210",
    "email": "priya@example.com", "crew_kind": "Volunteer",
    "date": "14 Nov 2026", "time": "10:00 – 17:00", "venue": "Tinkerspace, Main Hall", "price": "INR 500",
    "order": "ORD-1042",
    "unit": "Kochi", "unit_code": "KOC", "units": "North / Kochi", "level1": "North", "level2": "Kochi",
    "level3": "", "level4": "", "roles": "Technician", "machine_scope": "Laser cutters",
}
SAMPLE_LONG = {
    **SAMPLE_SHORT,
    "name": "Alexandra Montgomery-Fitzgerald", "plan": "Annual supporting member (concession)",
    "title": "Senior Community Partnerships Lead", "team": "The Midnight Debugging Collective",
    "track": "Assistive technology and accessibility", "event": "Community Hardware Hackathon 2026",
    "space": "Thiruvananthapuram Community Makerspace", "organisation": "International Federation of Community Builders",
    "programme": "Volunteer and mentor identification", "emergency_contact": "Ramachandran Pillai · +91 98765 43210",
    "email": "alexandra.montgomery-fitzgerald@example.com",
    "units": "Northern Region / Greater Thiruvananthapuram Chapter", "roles": "Space Manager, Technician, Event Manager",
    "machine_scope": "Laser cutters, 3D printers and 4 more",
}


def valid_tag(tag):
    if tag in TAGS or tag in SENSITIVE_TAGS:
        return True
    return tag.startswith(ANSWER_PREFIX) and bool(_ANSWER_KEY.match(tag[len(ANSWER_PREFIX):]))


def tags_in(text):
    return [match.strip() for match in _TAG.findall(text)]


def validate_text(text, *, limit=500):
    if not isinstance(text, str) or len(text) > limit:
        raise ValidationError({"text": gettext('Use at most {limit} characters.').format(limit=limit)})
    for tag in tags_in(text):
        if not valid_tag(tag):
            raise ValidationError({"text": gettext('Unknown data field {{{{{tag}}}}}.').format(tag=tag)})
    if re.search(r"[{}]", _TAG.sub("", text)):
        raise ValidationError({"text": gettext("Braces are only used around a data field, like {{name}}.")})
    return text


def merge(text, values, *, allow_sensitive=False):
    """Replace each tag with its value; an unknown or withheld tag renders empty."""
    def replace(match):
        tag = match.group(1).strip()
        if tag in SENSITIVE_TAGS and not allow_sensitive:
            return ""
        value = values.get(tag)
        return "" if value is None else str(value)

    return _TAG.sub(replace, text)


def uses_sensitive(document):
    for side in ("front", "back"):
        for layer in document.get(side, {}).get("layers", ()):
            text = layer.get("text") or ""
            if any(tag in SENSITIVE_TAGS for tag in tags_in(text)):
                return True
    return False
