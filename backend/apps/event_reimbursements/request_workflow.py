"""Sole request writer, including same-transaction canonical submit hooks."""
import json
from django.utils import timezone
from apps.events.models import EventRegistration, HackathonApplication
from apps.payments.event_payouts.errors import require
from .config_models import ReimbursementProgramme
from .request_models import GrantRequest
from .request_form_adapter import recheck_locked
from .transactions import command, changed, require_outer


def subject_locked(*, event, actor, registration=None, application=None, phase):
    require(registration is not None or application is not None, "canonical_participation_required")
    for subject in (registration, application):
        if subject:
            require(subject.event_id == event.pk and subject.member_id == actor.pk, "invalid_subject", status=404)
    if application and registration:
        require(application.registration_id == registration.pk, "invalid_subject", status=404)
    if phase == "after_acceptance":
        require(registration is not None and registration.status in ("registered", "attended"), "participation_not_accepted")
        if application:
            require(application.state == "confirmed", "participation_not_accepted")
    elif application:
        require(application.state != "draft", "reimbursement_submit_only", status=400)


def submit_application_locked(*, event, actor, prepared, registration, application=None, locks):
    require_outer(locks, event)
    from apps.makerspaces.guards import require_module_locked
    require_module_locked(event.makerspace, "event_reimbursements")
    programme = ReimbursementProgramme.objects.select_for_update().get(event=event)
    recheck_locked(prepared, programme=programme, event=event, actor=actor, phase="application")
    subject_locked(event=event, actor=actor, registration=registration, application=application, phase="application")
    require(not GrantRequest.objects.filter(programme=programme, member=actor).exists(), "reimbursement_request_exists")
    return _create_locked(event=event, actor=actor, prepared=prepared, programme=programme,
                          registration=registration, application=application, phase="application")


def _create_locked(*, event, actor, prepared, programme, registration, application, phase, draft=None):
    from apps.audit.services import record
    value, now = prepared.normalized, timezone.now()
    itinerary = value["itinerary"]
    row = draft or GrantRequest(programme=programme, event=event, member=actor, currency=programme.currency)
    row.registration, row.application, row.request_phase = registration, application, phase
    row.creation_operation_id = prepared.operation_id
    row.origin, row.destination, row.mode = itinerary["origin"] or "", itinerary["destination"] or "", itinerary["mode"]
    row.need_statement, row.itinerary = value["need_statement"], json.dumps(itinerary)
    row.estimated_cost = json.dumps({"form": value["form"], "snapshot": prepared.snapshot,
        "consent": True, "submitted_at": now.isoformat(), "distance_self_reported": True})
    row.distance_km = value.get("distance_km")
    row.category_estimates = value["estimates"]
    row.estimated_total_minor = sum(item["amount_minor"] for item in value["estimates"])
    row.submitted_at, row.state = now, "requested"
    if draft:
        row.version += 1
    row.save()
    record(actor, "event.reimbursement.requested", makerspace=event.makerspace, target=row,
           meta={"request_id": row.pk, "old_state": "draft", "new_state": row.state})
    return row


def submit(*, event_id, actor, data, prepared):
    with command(event_id=event_id, actor=actor, data=data, action="request.submit", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        programme = ReimbursementProgramme.objects.select_for_update().get(event=ctx.event)
        recheck_locked(prepared, programme=programme, event=ctx.event, actor=ctx.actor, phase="after_acceptance")
        registration = EventRegistration.objects.filter(event=ctx.event, member=actor,
            status__in=("registered", "attended")).first()
        application = HackathonApplication.objects.filter(event=ctx.event, member=actor).first()
        subject_locked(event=ctx.event, actor=actor, registration=registration, application=application,
                       phase="after_acceptance")
        row = GrantRequest.objects.select_for_update().filter(programme=programme, member=actor).first()
        require(row is None or row.state == "draft", "reimbursement_request_exists")
        require(data["expected_version"] == (row.version if row else 0), "stale_version")
        row = _create_locked(event=ctx.event, actor=ctx.actor, prepared=prepared, programme=programme,
            registration=registration, application=application, phase="after_acceptance", draft=row)
        return ctx.finish(row, uuid=str(row.uuid))


def withdraw(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="request.withdraw", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        row = GrantRequest.objects.select_for_update().get(event=ctx.event, member=actor)
        ctx.cas(row)
        require(row.state in ("draft", "requested", "waitlisted"), "request_not_withdrawable")
        old = row.state
        changed(row, state="withdrawn")
        ctx.audit("event.reimbursement.request_withdrawn", row, old_state=old, new_state=row.state)
        return ctx.finish(row)


def create_draft(*, event_id, actor, data):
    with command(event_id=event_id, actor=actor, data=data, action="request.draft", owner=True) as ctx:
        if ctx.replay:
            return ctx.replay
        programme = ReimbursementProgramme.objects.select_for_update().get(event=ctx.event, enabled=True)
        existing = GrantRequest.objects.select_for_update().filter(programme=programme, member=ctx.actor).first()
        if existing:
            ctx.cas(existing)
            return ctx.finish(existing, uuid=str(existing.uuid))
        require(data["expected_version"] == 0, "stale_version")
        registration = EventRegistration.objects.filter(event=ctx.event, member=ctx.actor,
            status__in=("registered", "attended")).first()
        application = HackathonApplication.objects.filter(event=ctx.event, member=ctx.actor).first()
        subject_locked(event=ctx.event, actor=ctx.actor, registration=registration, application=application,
                       phase="after_acceptance")
        row = GrantRequest.objects.create(programme=programme, event=ctx.event, member=ctx.actor,
            registration=registration, application=application, currency=programme.currency,
            request_phase="after_acceptance", mode="")
        ctx.audit("event.reimbursement.request_draft_created", row, request_id=row.pk)
        return ctx.finish(row, uuid=str(row.uuid))
