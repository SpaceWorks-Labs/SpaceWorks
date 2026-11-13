"""Merge tags a card design may place, and the sample values the designer previews.

Values come from a frozen snapshot assembled at render time by the holder adapter
(`holders.py`); a design never names a model field. `field:<key>` places a programme
or event answer. The two sensitive tags render only when the holder opted in (§3.4).
"""
from contextlib import contextmanager
from contextvars import ContextVar
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
    # Card Studio: the holder's name split for two-weight names ("FATHIMA" light + "SHENZA" bold).
    "first_name", "last_name",
)
# Certificate designs (decision 315) add these; a card design may not place them. `recipient` is the certificate's
# name for `name`; `serial` is the certificate number and `verify_url` the public verification page.
CERTIFICATE_TAGS = ("recipient", "event_date", "issue_date", "kind", "award", "place", "hours", "achievement",
                    "serial", "serial_short")
_DOCUMENT_KIND = ContextVar("card_document_kind", default="card")
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
    "first_name": "Priya", "last_name": "Raman",
    "unit": "Kochi", "unit_code": "KOC", "units": "North / Kochi", "level1": "North", "level2": "Kochi",
    "level3": "", "level4": "", "roles": "Technician", "machine_scope": "Laser cutters",
}
SAMPLE_LONG = {
    **SAMPLE_SHORT,
    "name": "Alexandra Montgomery-Fitzgerald", "first_name": "Alexandra", "last_name": "Montgomery-Fitzgerald", "plan": "Annual supporting member (concession)",
    "title": "Senior Community Partnerships Lead", "team": "The Midnight Debugging Collective",
    "track": "Assistive technology and accessibility", "event": "Community Hardware Hackathon 2026",
    "space": "Thiruvananthapuram Community Makerspace", "organisation": "International Federation of Community Builders",
    "programme": "Volunteer and mentor identification", "emergency_contact": "Ramachandran Pillai · +91 98765 43210",
    "email": "alexandra.montgomery-fitzgerald@example.com",
    "units": "Northern Region / Greater Thiruvananthapuram Chapter", "roles": "Space Manager, Technician, Event Manager",
    "machine_scope": "Laser cutters, 3D printers and 4 more",
}
# Designer-preview values for a certificate (the certificate engine's own sample set; the card samples above are untouched).
CERTIFICATE_SAMPLE = {
    **SAMPLE_SHORT, "recipient": "Priya Raman", "event_date": "14 November 2026", "issue_date": "2 December 2026",
    "kind": "Participant", "award": "Best hardware hack", "place": "1st place", "hours": "6",
    "achievement": "1st place - Best hardware hack", "serial": "SW-2026-000042", "serial_short": "SW-2026-",
}


@contextmanager
def document_kind(kind):
    """`normalize_document` runs inside this so a certificate design may use the certificate tags."""
    token = _DOCUMENT_KIND.set(kind)
    try:
        yield
    finally:
        _DOCUMENT_KIND.reset(token)


def valid_tag(tag):
    if tag in TAGS or tag in SENSITIVE_TAGS:
        return True
    if tag in CERTIFICATE_TAGS:
        return _DOCUMENT_KIND.get() == "certificate"
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
        if value is None and tag in ("first_name", "last_name"):
            first, _, rest = str(values.get("name") or "").strip().partition(" ")
            value = first if tag == "first_name" else rest.strip()
        return "" if value is None else str(value)

    return _TAG.sub(replace, text)


def uses_sensitive(document):
    for side in ("front", "back"):
        for layer in document.get(side, {}).get("layers", ()):
            text = layer.get("text") or ""
            if any(tag in SENSITIVE_TAGS for tag in tags_in(text)):
                return True
    return False
