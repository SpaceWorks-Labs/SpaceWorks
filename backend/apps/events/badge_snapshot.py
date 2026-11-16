"""The badge projection shared by the event card holder and the offline roster (parity E-B2).

One function decides what a badge may carry, so a printed card, a desk print and the encrypted offline roster can
never disagree. Privacy rules (SPEC §4.4, decision 294):

* the email is included only when the resolved design actually prints it;
* a registration answer (`field:<key>`) is included only when the design prints that exact key AND the question
  is not marked sensitive in the registration form;
* the roster carries the same, nothing more, plus a reference to a consented photo (never the bytes).
"""
import json

from django.utils.translation import gettext

ANSWER_PREFIX = "field:"
MAX_VALUE = 120


def printed_tags(document):
    """Every data tag a design prints, whether placed as a data field layer or inside a text layer."""
    from apps.card_designs.data_fields import tags_in
    from apps.card_designs.layout import sides
    tags = set()
    for side in sides(document):
        for layer in document[side]["layers"]:
            if layer.get("field"):
                tags.add(layer["field"])
            tags.update(tags_in(layer.get("text") or ""))
    return tags


def allowed_keys(event):
    """-> (set of printable question keys, True when a form exists). Sensitive and file questions are excluded."""
    from .models import EventFormRevision
    row = EventFormRevision.objects.filter(event=event, form_key="registration").order_by("-revision").first()
    schema = row.schema if row else None
    questions = (schema.get("questions") or schema.get("fields")) if isinstance(schema, dict) else schema
    if not questions:
        return set(), False
    keys = set()
    for item in questions:
        if isinstance(item, dict) and not item.get("sensitive") and item.get("type") != "file":
            key = item.get("key") or item.get("id")
            if key:
                keys.add(str(key))
    return keys, True


def _answers(registration):
    raw = registration.custom_answers
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return {}
    if not isinstance(raw, dict):
        return {}
    if raw.get("version") == 2:
        return {str(row.get("id")): row.get("value") for row in raw.get("answers") or ()
                if isinstance(row, dict) and "derivation_id" not in row}
    return {str(key): value for key, value in raw.items()}


def _text(value):
    if isinstance(value, bool):
        return gettext("Yes") if value else gettext("No")
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value if isinstance(item, (str, int, float)))
    if not isinstance(value, (str, int, float)):
        return ""
    return str(value).strip()[:MAX_VALUE]


def answer_values(event, registration, tags, form=None):
    """`field:<key>` -> printed text, only for keys the design prints and the form allows.

    `form` is `allowed_keys(event)` computed once by a caller that projects many registrations."""
    wanted = {tag[len(ANSWER_PREFIX):] for tag in tags if tag.startswith(ANSWER_PREFIX)}
    if not wanted:
        return {}
    allowed, has_form = form if form is not None else allowed_keys(event)
    answers = _answers(registration)
    result = {}
    for key in wanted:
        if has_form and key not in allowed:
            continue
        text = _text(answers.get(key))
        if text:
            result[ANSWER_PREFIX + key] = text
    return result


def crew_text(event, registration):
    """The crew chip ("Volunteer · Door", "Mentor", "Crew") or "" for a non-crew registration."""
    from .contributions.crew_reads import crew_labels
    return crew_labels(event, [registration.pk]).get(registration.pk, "")


def projection(event, registration, tags, *, crew=None, form=None):
    """The registration-derived badge values: crew text, email (if printed) and printed answers.

    `crew` (the crew chip text) and `form` are optional precomputed values for bulk callers (the roster)."""
    values = {"crew_kind": crew_text(event, registration) if crew is None else crew}
    if "email" in tags:
        values["email"] = registration.email or ""
    values.update(answer_values(event, registration, tags, form))
    return values


def sponsor_logos(event, limit=6):
    """Active sponsors' logos in order (public image bucket), as PNG bytes keyed sponsor_1..sponsor_N."""
    from apps.card_designs.images import read_public_image
    from .contributions.models_roles import EventSponsor
    rows = EventSponsor.objects.filter(event=event, active=True).exclude(logo_reference="").order_by("pk")
    logos = {}
    for row in rows[:limit]:
        data = read_public_image(row.logo_reference)
        if data:
            logos[f"sponsor_{len(logos) + 1}"] = data
    return logos
