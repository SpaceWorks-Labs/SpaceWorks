"""A programme's join-form questions (<= 12) and the answers checked against them.

Each question: key, label, type (text | choice | email | phone), required, options (choice
only), placement (front | back | hidden: whether the answer may appear on the card) and
an optional Saved-details key used to prefill it (#28). Answers are scoped PII.
"""
from django.utils.translation import gettext
import re

from rest_framework.exceptions import ValidationError

from .prefill import allowed as prefill_allowed

KEY = re.compile(r"^[a-z0-9_]{1,40}$")
TYPES = ("text", "choice", "email", "phone")
PLACEMENTS = ("front", "back", "hidden")
MAX_QUESTIONS = 12


def validate_schema(value):
    if not isinstance(value, list) or len(value) > MAX_QUESTIONS:
        raise ValidationError({"form_schema": gettext('Use at most {MAX_QUESTIONS} questions.').format(MAX_QUESTIONS=MAX_QUESTIONS)})
    clean, seen = [], set()
    for index, question in enumerate(value):
        if not isinstance(question, dict):
            raise ValidationError({"form_schema": gettext('Question {value} is not an object.').format(value=index + 1)})
        key, label = question.get("key"), question.get("label")
        kind = question.get("type", "text")
        if not isinstance(key, str) or not KEY.match(key) or key in seen:
            raise ValidationError({"form_schema": gettext('Question {value} needs a unique key (a-z, 0-9, _).').format(value=index + 1)})
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 120 or kind not in TYPES:
            raise ValidationError({"form_schema": gettext('Question {value} needs a label and a known type.').format(value=index + 1)})
        options = question.get("options", [])
        if kind == "choice" and (not isinstance(options, list) or not 1 <= len(options) <= 20
                                 or any(not isinstance(item, str) or len(item) > 80 for item in options)):
            raise ValidationError({"form_schema": gettext('Question {value} needs 1-20 short options.').format(value=index + 1)})
        placement = question.get("placement", "hidden")
        if placement not in PLACEMENTS:
            raise ValidationError({"form_schema": gettext('Question {value}: place the answer front, back or hidden.').format(value=index + 1)})
        saved = question.get("saved_details_key", "")
        if not isinstance(saved, str) or (saved and not prefill_allowed(saved)):
            raise ValidationError({"form_schema": gettext('Question {value}: choose a Saved detail that may fill it.').format(value=index + 1)})
        seen.add(key)
        clean.append({"key": key, "label": label.strip(), "type": kind, "required": bool(question.get("required")),
                      "options": options if kind == "choice" else [], "placement": placement,
                      "saved_details_key": saved})
    return clean


def validate_answers(schema, raw):
    raw = raw if isinstance(raw, dict) else {}
    answers = {}
    for question in schema or ():
        value = raw.get(question["key"], "")
        value = "" if value is None else str(value).strip()
        if not value:
            if question.get("required"):
                raise ValidationError({"answers": gettext('“{value}” is required.').format(value=question['label'])})
            continue
        if len(value) > 500:
            raise ValidationError({"answers": gettext('“{value}” is too long.').format(value=question['label'])})
        if question["type"] == "choice" and value not in question["options"]:
            raise ValidationError({"answers": gettext('Choose one of the options for “{value}”.').format(value=question['label'])})
        if question["type"] == "email" and "@" not in value:
            raise ValidationError({"answers": gettext('“{value}” needs an email address.').format(value=question['label'])})
        answers[question["key"]] = value
    return answers
