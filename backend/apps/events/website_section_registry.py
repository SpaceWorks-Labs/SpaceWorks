"""Closed editorial section options; programme reads retain their own live gates."""
from rest_framework.exceptions import ValidationError
from .programme_sections.providers import KINDS, validate_options as programme_options


def validate_options(kind, value):
    if kind not in KINDS:
        if value != {}:
            raise ValidationError({"options": "This section has no supported options."})
        return {}
    try:
        return programme_options(value)
    except ValueError as exc:
        raise ValidationError({"options": str(exc)}) from exc
