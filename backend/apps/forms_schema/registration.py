"""Ordinary-registration error compatibility for G's single-normalization adapter.

No Events import: the caller supplies the opaque typed subject. New application
and contribution endpoints call validate_submission directly for fields errors.
"""
from rest_framework.exceptions import ValidationError
from .submission import validate_submission


def validate_registration_member_input(*, schema, payload, subject):
    kind = getattr(subject, "kind", None)
    if getattr(kind, "value", kind) != "registration":
        raise TypeError("Use the ordinary registration subject adapter.")
    try:
        return validate_submission(schema=schema, payload=payload, subject=subject)
    except ValidationError as exc:
        detail = exc.detail
        if isinstance(detail, dict):
            if "custom_answers" in detail:
                raise ValidationError({"answers": detail["custom_answers"]}) from exc
            if detail.get("code") in {"invalid_answer", "derived_value_not_accepted", "duplicate_profile_mapping"}:
                raise ValidationError({"answers": detail.get("fields", {})}) from exc
        raise
