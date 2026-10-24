"""Transactional registration lifecycle transitions."""

from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.events.capacity import registration_spots_left
from apps.events.cancellation_policy import member_can_cancel
from apps.events.exceptions import CapacityConflict, EventInvalidTransition
from apps.events.models import Event, EventRegistration
from apps.events.service_payments import (
    create_for_registered_registration,
)
from apps.events.services_calendar import calendar_registration_changed
from apps.makerspaces.guards import require_module_locked
from apps.operations.cancellation_restore import record_cancellation


from .registration_locks import _boundary, _lock_registration
from .services_registration_fences import _fence
from .services_write_boundary import event_write
from .hackathons.admission_bridge import require_ordinary_transition, requires_admission


def _decision_is_open(event):
    return event.status == Event.Status.PUBLISHED and timezone.now() < event.ends_at


def _lock_waiters(event):
    return list(
        EventRegistration.objects.select_for_update()
        .filter(event=event, status=EventRegistration.Status.WAITLISTED)
        .order_by(Coalesce("waitlist_position_at", "created_at"), "id")
    )


def _promote(event, actor, waiters, count=None, *, mode):
    services = _boundary()
    selected = []
    for registration in waiters:
        require_ordinary_transition(registration)
        if count is not None and len(selected) >= count:
            break
        from .organization_audience import OrganizationAudienceRefused, require_queued_admission
        from .host_waivers import HostWaiverRequired
        try:
            require_queued_admission(event, registration)
        except (OrganizationAudienceRefused, HostWaiverRequired):
            if mode == "automatic_fifo":
                continue
            raise
        available = registration_spots_left(event, registration.ticket_type)
        if available is not None and available <= 0:
            continue
        selected.append(registration)
        registration.event = event
        registration.status = EventRegistration.Status.REGISTERED
        registration.version += 1
        registration.save(update_fields=["status", "version"])
        calendar_registration_changed(registration)
        create_for_registered_registration(registration, actor)
        from .services_registration_preparation import issue_ordinary_credential_locked
        issue_ordinary_credential_locked(event, registration, actor=actor)
        meta = {"registration_id": registration.pk, "promotion_mode": mode}
        services._audit(
            event, actor, "event.registration_promoted", registration, meta
        )
        services.notify_event_lifecycle(
            event, "registration_promoted", registration.pk
        )
    return selected


def promote_automatically(event, actor, count=None):
    if requires_admission(event.pk):
        from .hackathons.admission_lifecycle import promote_event_locked
        from .programme_locks import current_locks
        promote_event_locked(event=event, actor=actor, locks=current_locks(event.pk))
        return []
    _fence(event)
    if event.registration_requires_approval:
        return []
    return _promote(
        event, actor, _lock_waiters(event), count, mode="automatic_fifo"
    )


@event_write(permission="manage_registrations")
def approve_registration(registration, *, actor):
    services = _boundary()
    event = services._locked_event(registration.event_id, lock_makerspace=False)
    _fence(event)
    locked = _lock_registration(event, registration.pk)
    require_ordinary_transition(locked)
    if (
        not event.registration_requires_approval
        or locked.status != EventRegistration.Status.PENDING_APPROVAL
        or not _decision_is_open(event)
    ):
        raise EventInvalidTransition("This registration cannot be approved.")
    from .organization_audience import require_queued_admission
    require_queued_admission(event, locked)
    available = registration_spots_left(event, locked.ticket_type)
    new_status = (
        EventRegistration.Status.REGISTERED
        if available is None or available > 0
        else EventRegistration.Status.WAITLISTED
    )
    locked.status = new_status
    locked.version += 1
    locked.save(update_fields=["status", "version"])
    calendar_registration_changed(locked)
    if new_status == EventRegistration.Status.REGISTERED:
        create_for_registered_registration(locked, actor)
        from .services_registration_preparation import issue_ordinary_credential_locked
        issue_ordinary_credential_locked(event, locked, actor=actor)
    services._audit(
        event,
        actor,
        "event.registration_approved",
        locked,
        {
            "registration_id": locked.pk,
            "old_status": EventRegistration.Status.PENDING_APPROVAL,
            "new_status": new_status,
            "capacity_result": (
                "confirmed" if new_status == EventRegistration.Status.REGISTERED
                else "waitlisted_full"
            ),
        },
    )
    services.notify_event_lifecycle(event, "registration_approved", locked.pk)
    return services._refresh(locked)


@event_write(permission="manage_registrations")
def reject_registration(registration, *, actor):
    services = _boundary()
    event = services._locked_event(registration.event_id, lock_makerspace=False)
    _fence(event)
    locked = _lock_registration(event, registration.pk)
    require_ordinary_transition(locked)
    if locked.status not in (
        EventRegistration.Status.PENDING_APPROVAL,
        EventRegistration.Status.WAITLISTED,
    ):
        raise EventInvalidTransition("This registration cannot be rejected.")
    old_status = locked.status
    locked.status = EventRegistration.Status.REJECTED
    locked.version += 1
    locked.save(update_fields=["status", "version"])
    calendar_registration_changed(locked)
    services._audit(
        event,
        actor,
        "event.registration_rejected",
        locked,
        {
            "registration_id": locked.pk,
            "old_status": old_status,
            "new_status": EventRegistration.Status.REJECTED,
        },
    )
    services.notify_event_lifecycle(event, "registration_rejected", locked.pk)
    return services._refresh(locked)


@event_write(permission="manage_registrations")
def promote_registration(registration, *, actor):
    services = _boundary()
    event = services._locked_event(registration.event_id, lock_makerspace=False)
    _fence(event)
    locked = _lock_registration(event, registration.pk)
    require_ordinary_transition(locked)
    if (
        not event.registration_requires_approval
        or locked.status != EventRegistration.Status.WAITLISTED
        or not _decision_is_open(event)
    ):
        raise EventInvalidTransition("This registration cannot be promoted manually.")
    from .organization_audience import require_queued_admission
    require_queued_admission(event, locked)
    available = registration_spots_left(event, locked.ticket_type)
    if available is not None and available <= 0:
        raise CapacityConflict("No event capacity is available.")
    return services._refresh(
        _promote(event, actor, [locked], 1, mode="manual")[0]
    )


@event_write
def cancel_registration(registration, *, actor=None, member_cancel=False):
    services = _boundary()
    event = services._locked_event(registration.event_id, lock_makerspace=False)
    _fence(event)
    require_module_locked(event.makerspace_id, "events")
    locked = _lock_registration(event, registration.pk)
    if not member_cancel and actor is not None:
        # A staff actor must still hold the permission under the lock; actor=None is
        # a system cancellation (expiry, purge, payment lapse), as before part 4.
        from .event_authority import require
        require(actor, event, "manage_registrations")
    from .hackathons.admission_lifecycle import cancel_registration_locked
    from .programme_locks import current_locks
    if cancel_registration_locked(event=event, registration=locked, actor=actor,
                                  member_cancel=member_cancel, locks=current_locks(event.pk)):
        return services._refresh(locked)
    if member_cancel and (
        actor is None or locked.member_id != actor.pk or not member_can_cancel(locked)
    ):
        raise EventInvalidTransition("The member cancellation deadline has passed.")
    if locked.status not in (
        EventRegistration.Status.PENDING_APPROVAL,
        EventRegistration.Status.REGISTERED,
        EventRegistration.Status.WAITLISTED,
    ):
        raise EventInvalidTransition("This registration cannot be cancelled.")
    old_status = locked.status
    provenance = record_cancellation(locked, now=timezone.now())
    locked.status = EventRegistration.Status.CANCELLED
    locked.version += 1
    locked.save(update_fields=["status", "version", *provenance])
    calendar_registration_changed(locked)
    services._audit(
        event,
        actor,
        "event.registration_cancelled",
        locked,
        {"registration_id": locked.pk, "old_status": old_status},
    )
    services.notify_event_lifecycle(event, "registration_cancelled", locked.pk)
    from .credentials.workflow import revoke_locked
    revoke_locked(locked, actor=actor, reason="cancelled")
    from .services_lifecycle import _cancel_open_charges_after_commit
    _cancel_open_charges_after_commit(event, actor, registration_ids=(locked.pk,))
    if (
        old_status == EventRegistration.Status.REGISTERED
        and not event.registration_requires_approval
        and services._may_promote(event, timezone.now())
    ):
        promote_automatically(event, actor, 1)
    return services._refresh(locked)


from .services_attendance_correction import correct_attendance
