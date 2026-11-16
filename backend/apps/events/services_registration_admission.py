"""Canonical registration writes used by hackathon admission, never by HTTP."""
from django.utils.translation import gettext
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .capacity import registration_spots_left
from .host_waivers import require_host_waiver, stamp_host_waiver
from .models import EventRegistration
from .programme_locks import assert_lock_context
from .registration_form_adapter import ValidatedRegistrationForm
from .services_calendar import calendar_registration_changed
from .services_core import _audit, _validate
from .hackathons.admission_errors import fail
from .hackathons.admission_models import HackathonApplication


def _application(application_id, registration_id, locks):
    assert_lock_context(locks)
    app = get_object_or_404(HackathonApplication, pk=application_id, event_id=locks.event_id,
                            registration_id=registration_id)
    if app.member_id not in locks.account_ids:
        raise RuntimeError("Declare the application owner before acquiring event locks.")
    row = get_object_or_404(EventRegistration.objects.select_for_update(),
                            pk=registration_id, event_id=locks.event_id, member_id=app.member_id)
    return app, row


def _snapshot(prepared, subject):
    if not isinstance(prepared.trusted_registration_form, ValidatedRegistrationForm):
        raise TypeError("Use the validated application form adapter.")
    prepared.trusted_registration_form.require_subject(subject)
    return prepared.snapshot


def _waiver(event, member, **kwargs):
    # Preserve shipped audience policy; ordinary account admission has no host
    # waiver requirement unless C's independent contributor requirements say so.
    if event.registration_audience != "participating_organizations":
        return None
    return require_host_waiver(event, member, **kwargs)


def create_pending_locked(*, event, member, selection, contacts, prepared, subject, locks):
    """Reuse ordinary quotes/access/waivers. Canonical answers are already validated."""
    from django.conf import settings
    from .registration_access import require_registration_access
    from .services_registration import _existing_registration, _quote, _record_registration
    from .ticketing import select_ticket
    from apps.accounts.account_kind_guards import require_member_account

    assert_lock_context(locks)
    if event.pk != locks.event_id or member.pk not in locks.account_ids:
        raise RuntimeError("Declare the application owner before admission.")
    require_member_account(member)
    if subject.event_id != event.pk or subject.owner_member_id != member.pk or subject.kind.value != "application":
        fail("not_found", gettext("Not found."), status=404)
    snapshot = _snapshot(prepared, subject)
    require_registration_access(event, member)
    values = selection.values
    app = get_object_or_404(HackathonApplication, event=event, member=member)
    if subject.subject_id is not None and subject.subject_id != app.pk:
        fail("not_found", gettext("Not found."), status=404)
    if app.registration_id:
        existing = get_object_or_404(EventRegistration.objects.select_for_update(),
            pk=app.registration_id, event=event, member=member, status="pending_approval")
        from .hackathons.admission_editing import require_unchanged_admission
        require_unchanged_admission(app, selection)
        waiver = _waiver(event, member, actor=member, registration=existing,
            **{key: values.get(key) for key in ("host_waiver_id", "host_waiver_version", "host_waiver_accepted")})
        existing.custom_answers, existing.version = snapshot, existing.version + 1
        existing.save(update_fields=["custom_answers", "version"])
        stamp_host_waiver(existing, waiver, actor=member, via=event.makerspace, event=event)
        _audit(event, member, "event.registration_answers_edited", existing)
        return existing.pk
    generation = event_hash = None
    if settings.PII_ENCRYPTION_ENABLED:
        from apps.encryption.blind_index import active_generation, event_email_hash
        generation = active_generation()
        event_hash = event_email_hash(contacts["email"], generation=generation.generation,
                                     makerspace_id=event.makerspace_id, event_id=event.pk)
    existing = _existing_registration(event, member, contacts["email"], generation, event_hash)
    if existing is not None:
        if existing.member_id != member.pk:
            fail("contact_unavailable", gettext("This contact cannot be used for this registration."), status=400)
        if existing.status not in ("cancelled", "rejected"):
            fail("admission_mapping_conflict", gettext("Use the existing application registration."))
        _require_reusable(existing)
    waiver = _waiver(event, member, actor=member, registration=existing,
        **{key: values.get(key) for key in ("host_waiver_id", "host_waiver_version", "host_waiver_accepted")})
    ticket = select_ticket(event, values.get("ticket_type_id"), member)
    require_participant_ticket(event, ticket)
    quote = _quote(event, member, ticket, values.get("invite_code"), values.get("promo_code"), actor=member, admission_locked=True)
    from .credentials.preparation import new_registration_id
    row = existing or EventRegistration(pk=new_registration_id(event.pk), event=event, member=member)
    row.event = event
    for field, value in quote.items():
        setattr(row, field, value)
    row.name = member.display_name or member.get_full_name() or member.username
    row.email, row.phone = contacts["email"], contacts["phone"]
    row.registered_via_makerspace = row.payment_via_makerspace = event.makerspace
    row.status, row.custom_answers, row.credential_mode = "pending_approval", snapshot, "inert"
    row.cancelled_at, row.status_before_cancel, row.waitlist_position_at = None, "", None
    row.version += bool(existing)
    _validate(row)
    row.save()
    stamp_host_waiver(row, waiver, actor=member, via=event.makerspace, event=event)
    calendar_registration_changed(row)
    _record_registration(event, member, row, row.status)
    return row.pk


def _require_reusable(row):
    from apps.payments.models import Payment
    had_seat = row.status == "cancelled" and row.status_before_cancel not in ("pending_approval", "waitlisted")
    if (had_seat and (row.quoted_amount or 0) > 0) or Payment.objects.filter(
            makerspace_id=row.event.makerspace_id, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id=row.pk).exists():
        fail("paid_registration_retained", gettext("A paid registration cannot be reused. Contact staff."))


def mirror_answers_locked(*, application_id, registration_id, prepared, locks):
    app, row = _application(application_id, registration_id, locks)
    # Prepared binding may carry the creation operation instead of the new PK.
    if prepared.subject.event_id != app.event_id or prepared.subject.owner_member_id != app.member_id:
        fail("not_found", gettext("Not found."), status=404)
    if prepared.subject.subject_id is not None and prepared.subject.subject_id != app.pk:
        fail("not_found", gettext("Not found."), status=404)
    row.custom_answers = _snapshot(prepared, prepared.subject)
    row.version += 1
    row.save(update_fields=["custom_answers", "version"])
    _audit(row.event, row.member, "event.registration_answers_edited", row)


def transition_locked(*, application_id, registration_id, transition, actor, reason_code, locks):
    """Admission chooses the transition; this registration service alone writes it."""
    app, row = _application(application_id, registration_id, locks)
    event = row.event
    targets = {"offer": "pending_approval", "waitlist": "waitlisted", "confirm": "registered",
               "reject": "rejected", "cancel": "cancelled", "event_cancel": "cancelled", "reopen": "pending_approval"}
    allowed = {"offer": ("pending_approval", "waitlisted"), "waitlist": ("pending_approval", "waitlisted"),
               "confirm": ("pending_approval",), "reject": ("pending_approval", "waitlisted"),
               "cancel": ("pending_approval", "waitlisted", "registered"),
               "event_cancel": ("pending_approval", "waitlisted", "registered", "attended"),
               "reopen": ("pending_approval", "waitlisted", "registered", "cancelled", "rejected")}
    if transition not in targets:
        fail("invalid_transition", gettext("Unknown admission transition."))
    target, old = targets[transition], row.status
    # Owner command receipts normally absorb replay. Internal recovery is also safe.
    if old == target and transition not in ("offer", "reopen"):
        return row.pk
    if old not in allowed[transition]:
        fail("admission_mapping_conflict", gettext("The registration no longer matches this application."))
    if transition == "reopen":
        if old in ("registered", "waitlisted", "pending_approval"):
            from .event_authority import require
            require(actor, event, "review_applications")
        else:
            _require_reusable(row)
    if transition in ("offer", "confirm"):
        from .organization_audience import require_queued_admission
        require_queued_admission(event, row)
    if transition == "confirm":
        from .registration_access import require_registration_access
        from .hackathons.admission_transactions import require_member
        require_member(row.member)
        require_registration_access(event, row.member)
        if event.status != "published" or timezone.now() >= event.ends_at or app.date_review_required:
            fail("invalid_transition", gettext("This application cannot be confirmed."))
        available = registration_spots_left(event, row.ticket_type)
        if available is not None and available <= 0:
            fail("capacity_full", gettext("All confirmed places are taken. You can choose the waitlist."))
    row.status, row.version = target, row.version + 1
    if target == "cancelled":
        from apps.operations.cancellation_restore import record_cancellation
        record_cancellation(row, now=timezone.now())
    elif transition == "reopen":
        row.cancelled_at, row.status_before_cancel = None, ""
    row.save(update_fields=["status", "version", "cancelled_at", "status_before_cancel"])
    calendar_registration_changed(row)
    if transition == "reopen":
        from .credentials.workflow import revoke_locked
        revoke_locked(row, actor=actor, reason="admission_reopened")
    if target == "registered":
        from .service_payments import create_for_registered_registration
        from .credentials.workflow import issue_locked
        create_for_registered_registration(row, actor)
        from .credentials.preparation import prepared_issue
        issue_locked(event, row, actor=actor, prepared=prepared_issue(event.pk, row.pk))
    if target in ("cancelled", "rejected"):
        from .credentials.workflow import revoke_locked
        from .services_lifecycle import _cancel_open_charges_after_commit
        revoke_locked(row, actor=actor, reason=reason_code)
        _cancel_open_charges_after_commit(event, actor, registration_ids=(row.pk,))
    meta = {"registration_id": row.pk, "old_status": old, "new_status": target, "reason_code": reason_code}
    if transition == "offer":
        _audit(event, actor, "event.registration_approval_requested", row, meta)
    elif transition == "confirm":
        _audit(event, actor, "event.registration_approved", row, meta)
    elif transition in ("waitlist", "reopen"):
        _audit(event, actor, "event.registration_created", row, meta)
    elif transition == "reject":
        _audit(event, actor, "event.registration_rejected", row, meta)
    else:
        _audit(event, actor, "event.registration_cancelled", row, meta)
    return row.pk


def admit_contributor_locked(*, request, actor_id, operation_id, locks):
    """Explicit contributor admission still consumes event AND ticket hard seats."""
    from apps.accounts.models import User
    from .contributions.models_roles import EventRoleAssignment
    from .contributions.models_admission import EventContributorAdmission
    from .contributions.role_policy import require_requirements
    from .models import Event
    from .ticketing import select_ticket
    from .event_authority import require
    from .registration_access import require_registration_access
    from .services_registration import _quote, _record_registration

    assert_lock_context(locks)
    if request.event_id != locks.event_id or request.member_id not in locks.account_ids or actor_id not in locks.account_ids:
        raise RuntimeError("Declare contributor and issuer fences before admission.")
    if request.capacity_policy not in ("event_capacity", "reserved_contributor_capacity"):
        fail("invalid_capacity_policy", gettext("Choose an explicit contributor capacity policy."), status=400)
    event = Event.objects.get(pk=request.event_id)
    role = get_object_or_404(EventRoleAssignment, pk=request.assignment_id, event=event,
                            member_id=request.member_id, state="approved", imported_inert=False)
    member, actor = User.objects.get(pk=request.member_id), User.objects.get(pk=actor_id)
    require(actor, event, None)
    require_registration_access(event, member)
    require_requirements(actor_id=member.pk, assignment_id=role.pk, shift_id=None)
    if event.status != "published" or timezone.now() >= event.ends_at:
        fail("invalid_transition", gettext("This event no longer admits contributors."))
    ticket = select_ticket(event, request.ticket_type_id, member, contributor=True)
    if ticket is None or request.capacity_policy != ticket.contributor_capacity_policy:
        fail("contributor_ticket_required", gettext("Choose a matching contributor ticket policy."))
    if request.capacity_policy == "reserved_contributor_capacity":
        from . import capacity
        reserve = getattr(capacity, "require_contributor_room_locked", None)
        if reserve is None:
            fail("programme_dependency_unavailable", gettext("Contributor capacity reservations are temporarily unavailable."), status=503)
        reserve(event_id=event.pk, ticket_type_id=ticket.pk, assignment_id=role.pk, locks=locks)
    # A reserved policy reserves a distinct ticket pool; it never exempts the hard cap.
    ordinary = EventRegistration.objects.filter(event=event, ticket_type=ticket).exclude(
        pk__in=EventContributorAdmission.objects.filter(event=event).values("registration_id"))
    if ordinary.exists():
        fail("contributor_ticket_required", gettext("Choose a distinct contributor ticket type."))
    existing = EventRegistration.objects.select_for_update().filter(event=event, member=member,
        status__in=("registered", "attended", "pending_approval", "waitlisted")).first()
    if existing:
        if existing.ticket_type_id != ticket.pk or existing.status not in ("registered", "attended"):
            fail("admission_mapping_conflict", gettext("Use this member's existing admission workflow."))
        return existing.pk
    waiver = _waiver(event, member, actor=actor, allow_consent=False)
    available = registration_spots_left(event, ticket)
    if available is not None and available <= 0:
        fail("capacity_full", gettext("No contributor places are available."))
    quote = _quote(event, member, ticket, None, None, actor=actor, admission_locked=True)
    from .credentials.preparation import new_registration_id
    row = EventRegistration(pk=new_registration_id(event.pk), event=event, member=member, name=member.display_name or member.username,
        email=member.email, phone=member.phone, registered_via_makerspace=event.makerspace,
        payment_via_makerspace=event.makerspace, status="registered", credential_mode="inert", **quote)
    if not row.email or not row.phone:
        fail("contact_required", gettext("The contributor must supply contact details."), status=400)
    _validate(row)
    row.save()
    stamp_host_waiver(row, waiver, actor=actor, via=event.makerspace, event=event)
    _record_registration(event, actor, row, row.status)
    from .credentials.workflow import issue_locked
    from .credentials.preparation import prepared_issue
    issue_locked(event, row, actor=actor, prepared=prepared_issue(event.pk, row.pk))
    return row.pk


def require_participant_ticket(event, ticket):
    from .contributions.models_admission import EventContributorAdmission
    if ticket and (ticket.purpose == "contributor" or EventContributorAdmission.objects.filter(event=event, registration__ticket_type=ticket).exists()):
        fail("contributor_ticket_required", gettext("Choose a participant ticket type."), status=400)
