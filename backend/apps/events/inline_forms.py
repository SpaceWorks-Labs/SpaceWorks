"""Outer-command half of inline stage forms and the travel-support request block.

Registration and hackathon application submit both carry two optional blocks:
``stage_forms`` (application-stage forms answered with the signup) and
``reimbursement_request``. Each is prepared BEFORE the outer transaction (forms
validation and saved-detail intents may touch keys) and bound INSIDE it, after
the canonical registration/application rows exist, so a failure in either rolls
back the whole signup. Nothing here trusts a client-supplied binding proof.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from inspect import signature
from uuid import UUID, uuid5

from django.db import connection

from apps.payments.event_payouts.errors import PayoutError, require

INLINE_KEYS = ("stage_forms", "reimbursement_request")


@dataclass(frozen=True)
class PreparedInline:
    stages: tuple = ()
    request: object = None

    @property
    def empty(self):
        return not self.stages and self.request is None


EMPTY = PreparedInline()


def split_inline(data):
    """Remove the inline blocks so the base form validator never sees them."""
    return {key: data.pop(key) for key in INLINE_KEYS if key in data}


def request_operation_id(outer_operation_id, *, event_id, owner_id):
    return uuid5(outer_operation_id, f"events-reimbursement-request:v1:{event_id}:{owner_id}")


def _reimbursements_live(event):
    from apps.makerspaces.platform import module_enabled
    from apps.separability.registry import runtime_active
    return runtime_active("event_reimbursements") and module_enabled(event.makerspace, "event_reimbursements")


def prepare(*, event, actor, operation_id, inline, base_forms=None):
    """Validate both blocks outside any transaction; returns an in-process value only."""
    if not inline:
        return EMPTY
    require(not connection.in_atomic_block, "prepare_outside_transaction")
    if not isinstance(operation_id, UUID):
        raise PayoutError("operation_required", status=400)
    stages = ()
    if inline.get("stage_forms"):
        from apps.events.staged_forms.registration_hooks import prepare_inline
        from apps.events.staged_forms.inline_submission import validate_conflicts
        stages = prepare_inline(event=event, actor=actor, outer_operation_id=operation_id,
                                stage_forms=inline["stage_forms"])
        validate_conflicts(stages, base_forms=base_forms)
    request = None
    if inline.get("reimbursement_request") is not None:
        # An omitted block is harmless with the module off; a present one is refused.
        require(_reimbursements_live(event), "reimbursement_unavailable")
        from apps.event_reimbursements.config_models import ReimbursementProgramme
        from apps.event_reimbursements.request_form_adapter import prepare as prepare_request
        programme = ReimbursementProgramme.objects.filter(event=event).first()
        require(programme is not None, "reimbursement_unavailable")
        request = prepare_request(programme=programme, event=event, actor=actor,
            operation_id=request_operation_id(operation_id, event_id=event.pk, owner_id=actor.pk),
            block=inline["reimbursement_request"])
    return PreparedInline(stages, request)


def _requires_stage_binding(event):
    from apps.events.staged_forms.definition_models import EventStageForm
    return EventStageForm.objects.filter(event=event, state="published", stage="application", required=True).exists()


def bind_locked(*, event, actor, registration, application=None, prepared=EMPTY, locks):
    """Call inside the outer transaction after canonical rows exist, before its receipt."""
    result = {}
    if prepared.stages or _requires_stage_binding(event):
        from apps.events.staged_forms.registration_hooks import bind_inline_locked
        result.update(bind_inline_locked(event=event, actor=actor, registration=registration,
            application=application, prepared_stages=prepared.stages, locks=locks))
    if prepared.request is not None:
        require(_reimbursements_live(event), "reimbursement_unavailable")
        from apps.event_reimbursements.request_workflow import submit_application_locked
        row = submit_application_locked(event=event, actor=actor, prepared=prepared.request,
            registration=registration, application=application, locks=locks)
        result["reimbursement_request"] = {"id": row.pk, "uuid": str(row.uuid), "state": row.state}
    return result


_registration_inline = ContextVar("registration_inline", default=None)


def registration_inline(function):
    """Prepare a self-signup's inline blocks between form preparation and the write boundary."""
    parameters = signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        values = parameters.bind(*args, **kwargs).arguments
        inline, member, actor = values.get("inline_forms") or {}, values.get("member"), values.get("actor")
        self_signup = member is not None and actor is not None and getattr(actor, "pk", None) == member.pk
        if inline and not self_signup:
            raise PayoutError("owner_consent_required", status=400)
        if not self_signup:
            return function(*args, **kwargs)
        blocks = {key: inline[key] for key in INLINE_KEYS if key in inline}
        prepared = prepare(event=values["event"], actor=member, operation_id=inline.get("operation_id"), inline=blocks)
        token = _registration_inline.set(prepared)
        try:
            return function(*args, **kwargs)
        finally:
            _registration_inline.reset(token)
    return wrapped


def bind_registration_locked(event, registration):
    """Ordinary registration's in-transaction half; a no-op outside a self-signup."""
    prepared = _registration_inline.get()
    if prepared is None or (prepared.empty and not _requires_stage_binding(event)):
        return {}
    from apps.events.programme_locks import current_locks
    from apps.accounts.models import User
    return bind_locked(event=event, actor=User.objects.get(pk=registration.member_id), registration=registration,
                       prepared=prepared, locks=current_locks(event.pk))
