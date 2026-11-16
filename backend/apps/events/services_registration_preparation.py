"""Ordinary v2 forms prepare F/P state before the registration transaction."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from inspect import signature
from uuid import UUID

from rest_framework.exceptions import ValidationError

from .contracts.subjects import AnswerSubject, SubjectKind
from .models import EventRegistration

_prepared = ContextVar("ordinary_registration_form", default=None)


def ordinary_form(function):
    parameters = signature(function)
    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = parameters.bind(*args, **kwargs)
        values = bound.arguments
        # The member-account boundary comes first: a staff or platform account is refused
        # before any form preparation reads the event (account split M5).
        if values.get("member") is not None:
            from apps.accounts.account_kind_guards import require_member_account
            require_member_account(values["member"])
        target = values.get("event") or values.get("registration").event
        schema = target.custom_form
        if not isinstance(schema, dict) or schema.get("schema_version") != 2:
            if values.get("form_payload"):
                raise ValidationError({"code": "invalid_form_input"})
            return function(*args, **kwargs)
        member = values.get("member") or getattr(values.get("registration"), "member", None)
        if member is None:
            raise ValidationError({"code": "member_required"})
        existing = values.get("registration") or EventRegistration.objects.filter(event=target, member=member).first()
        if (values.get("repair_duplicate") and existing and existing.status in
                ("registered", "waitlisted", "pending_approval")):
            return function(*args, **kwargs)
        payload = dict(values.get("form_payload") or {})
        if "custom_answers" in payload and "answers" in payload:
            raise ValidationError({"code": "answer_field_conflict"})
        if "answers" not in payload:
            payload["answers"] = values.get("custom_answers")
        try:
            operation = UUID(str(payload["operation_id"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise ValidationError({"code": "operation_required"}) from exc
        actor = values.get("actor")
        if not isinstance(payload.get("save_choices", {}), dict) or not isinstance(payload.get("derivations", {}), dict):
            raise ValidationError({"code": "invalid_form_input"})
        if any(not isinstance(item, dict) for item in payload.get("derivations", {}).values()):
            raise ValidationError({"code": "invalid_form_input"})
        if actor and actor.pk != member.pk:
            # Private source derivation/owner review and vault consent belong
            # to the member, even when staff may edit ordinary raw event answers.
            if any(payload.get("save_choices", {}).values()) or payload.get("derivations"):
                raise ValidationError({"code": "owner_consent_required"})
        subject = AnswerSubject(event_id=target.pk, owner_member_id=member.pk,
            kind=SubjectKind.REGISTRATION, **({"subject_id": existing.pk} if existing else {"creation_operation_id": operation}))
        from .programme.prepared_forms import prepare
        prepared = prepare(actor_id=member.pk, subject=subject, schema=schema, payload=payload)
        token = _prepared.set(prepared)
        try:
            return function(*args, **kwargs)
        finally:
            _prepared.reset(token)
    return wrapped


def canonical_answers(event, raw):
    from apps.forms_schema.validation import validate_answers
    if not isinstance(event.custom_form, dict) or event.custom_form.get("schema_version") != 2:
        return validate_answers(event.custom_form, raw)
    from .registration_form_adapter import require_private_registration_answers
    from .programme.prepared_forms import require_current
    require_private_registration_answers()
    prepared = _prepared.get()
    if prepared is None:
        raise ValidationError({"code": "form_preparation_required"})
    require_current(prepared, event, event.custom_form)
    return prepared.snapshot


def attach_answers(event, registration):
    prepared = _prepared.get()
    if prepared is None:
        return
    from .programme.prepared_forms import apply_locked, require_current
    from .programme_locks import current_locks
    require_current(prepared, event, event.custom_form)
    subject = AnswerSubject(event_id=event.pk, owner_member_id=registration.member_id,
        kind=SubjectKind.REGISTRATION, subject_id=registration.pk)
    apply_locked(prepared, subject=subject, locks=current_locks(event.pk))
    issue_ordinary_credential_locked(event, registration, actor=registration.member)


def issue_ordinary_credential_locked(event, registration, *, actor=None):
    snapshot = registration.custom_answers
    if not isinstance(snapshot, dict) or snapshot.get("version") != 2:
        return
    if registration.status in ("registered", "attended"):
        from .credentials.workflow import issue_locked
        from .credentials.preparation import prepared_issue
        issue_locked(event, registration, actor=actor,
                     prepared=prepared_issue(event.pk, registration.pk))
    elif registration.credential_mode != "inert":
        registration.credential_mode = "inert"
        registration.save(update_fields=["credential_mode"])
