"""Single raw-answer spelling boundary for ordinary registration and A's bridge.

F supplies the validator; P prepares derivations before domain locks. This module
does not import either provider, provision keys, persist answers or enable v2.
Only internal code passes a ValidatedRegistrationForm to the future service
bridge; HTTP serializers must never accept a snapshot or a validated flag.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Callable, Mapping, Protocol

from rest_framework.exceptions import ValidationError

from .contracts.subjects import AnswerSubject


def require_private_registration_answers():
    """v2 must never fall through to the legacy unencrypted JSON column."""
    from django.apps import apps
    from django.db import models
    from apps.encryption.registry import field_for
    from .submissions.pii import PrivateDocumentMixin
    from .programme.commands import ProgrammeUnavailable
    model = apps.get_model("events.EventRegistration")
    if (not issubclass(model, PrivateDocumentMixin)
            or "custom_answers" not in model.pii_document_fields
            or not isinstance(model._meta.get_field("custom_answers"), models.TextField)
            or field_for(model, "custom_answers") is None):
        raise ProgrammeUnavailable("private_answer_storage_unavailable", "Private registration answer storage is unavailable.")


class MemberInputValidator(Protocol):
    def __call__(
        self, *, schema: object, payload: Mapping, subject: AnswerSubject,
    ) -> object:
        """Return F's validated member-input object, not a caller snapshot."""
        ...


@dataclass(frozen=True)
class NormalizedRegistrationInput:
    answer_field: str
    payload: dict = field(repr=False)


class ValidatedRegistrationForm:
    """In-process output of validate_registration_form, not a JSON authority flag."""

    __slots__ = ("subject", "answer_field", "_validated")

    def __init__(self, *, subject, answer_field, validated, _factory):
        if _factory is not _FACTORY:
            raise TypeError("Use validate_registration_form.")
        self.subject, self.answer_field = subject, answer_field
        self._validated = validated

    def require_subject(self, subject: AnswerSubject) -> object:
        if self.subject != subject:
            raise ValueError("Validated answers belong to another subject.")
        return self._validated


_FACTORY = object()


def _conflict(field):
    raise ValidationError({
        "code": "answer_field_conflict", "fields": {field: ["Use one raw answer map."]},
    })


def normalize_registration_input(
    payload: Mapping, *, schema_version: int, application: bool = False,
) -> NormalizedRegistrationInput:
    """Presence matters even for empty/null keys; never pick a winner silently."""
    if not isinstance(payload, Mapping):
        raise ValidationError({"code": "invalid_form_input", "fields": {}})
    if "custom_answers" in payload and (application or "answers" in payload):
        _conflict("custom_answers")
    field_name = "answers" if "answers" in payload or application else "custom_answers"
    data = deepcopy(dict(payload))
    raw = data.pop("custom_answers", None) if field_name == "custom_answers" else data.get("answers")
    if schema_version not in (1, 2) or (
        schema_version == 1 and "answers" in payload and not application
    ):
        raise ValidationError({field_name: ["Use the matching form schema version."]})
    if raw is not None and not isinstance(raw, dict):
        raise ValidationError({field_name: ["Expected a question-ID map."]})
    if (isinstance(raw, dict) and isinstance(raw.get("answers"), list)
            and {"version", "form_id", "form_revision", "answers"} <= raw.keys()):
        raise ValidationError({field_name: ["Canonical snapshots are server-owned."]})
    data["answers"] = raw
    return NormalizedRegistrationInput(field_name, data)


def validate_registration_form(
    payload: Mapping, *, schema: object, subject: AnswerSubject,
    validator: MemberInputValidator, application: bool = False,
) -> ValidatedRegistrationForm:
    version = schema.get("schema_version") if isinstance(schema, dict) else 1
    if version == 2 and not application:
        require_private_registration_answers()
    normalized = normalize_registration_input(
        payload, schema_version=version, application=application,
    )
    try:
        validated = validator(schema=schema, payload=normalized.payload, subject=subject)
    except ValidationError as exc:
        # Old callers retain custom_answers; nested compound errors stay intact.
        if normalized.answer_field == "custom_answers" and isinstance(exc.detail, dict):
            errors = dict(exc.detail)
            if "answers" in errors:
                errors["custom_answers"] = errors.pop("answers")
            raise ValidationError(errors) from exc
        raise
    return ValidatedRegistrationForm(
        subject=subject, answer_field=normalized.answer_field,
        validated=validated, _factory=_FACTORY,
    )


def validate_legacy_answers(schema, custom_answers, *, validator: Callable):
    """Direct raw-service callers retain the shipped validation path."""
    return validator(schema, custom_answers)
