from django.db import transaction
from django.utils import timezone

from apps.events.exceptions import EventInvalidTransition
from apps.events.models import (
    Event,
    EventAttendanceCertificate,
    EventFeedbackSurvey,
)
from apps.events.services_calendar import calendar_event_changed
from apps.makerspaces import limits
from apps.makerspaces.guards import require_module_locked
from .services_write_boundary import event_write
from .programme_locks import current_locks


def _boundary():
    from apps.events import services

    return services


def _lock_series_first(event_id):
    """Occurrence writers take series -> occurrence, the order series edits use.

    A second write to the occurrence row in one transaction makes PostgreSQL
    re-check its series FK (FOR KEY SHARE) at commit; without the series lock
    first, that check deadlocks against a concurrent series edit waiting on
    this occurrence.
    """
    from apps.events.models import EventSeries
    series_id = Event.objects.values_list("series_id", flat=True).get(pk=event_id)
    if series_id:
        EventSeries.objects.select_for_update().get(pk=series_id)


def _transition(event, actor, expected, new_status, action):
    services = _boundary()
    _lock_series_first(event.pk)
    locked = services._locked_event(event.pk)
    if locked.status != expected:
        message = f"Cannot transition event from {locked.status} to {new_status}."
        raise EventInvalidTransition(message)
    locked.status = new_status
    locked.version += 1
    locked.save(update_fields=["status", "version", "updated_at"])
    calendar_event_changed(locked)
    meta = {"old_status": expected, "new_status": new_status}
    services._audit(locked, actor, action, locked, meta)
    services.notify_event_lifecycle(locked, new_status)
    return services._refresh(locked)


@event_write
def publish(event, *, actor, publish_website=False, website_revision=None, publish_without_room=False):
    services = _boundary()
    _lock_series_first(event.pk)
    locked = services._locked_event(event.pk)
    if locked.status != Event.Status.DRAFT:
        raise EventInvalidTransition("Only draft events can be published.")
    services._validate(locked)
    if locked.ends_at < timezone.now():
        raise EventInvalidTransition("Ended events cannot be published.")
    locked.makerspace = require_module_locked(locked.makerspace, "events")
    from .staff_grant_locks import lock_authority
    actor = lock_authority(actor, locked)
    from .event_authority import require
    from .event_permissions import PUBLISH_SCHEDULE
    require(actor, locked, PUBLISH_SCHEDULE)
    from .registration_access import validate_event_audience
    validate_event_audience(locked)
    from .audience_default import apply_membership_off_fallback
    from .venue_publish_check import enforce_on_publish
    fell_back = apply_membership_off_fallback(locked)  # decision 223: never publish an event nobody can join
    venue = enforce_on_publish(locked, publish_without_room=publish_without_room)  # decision 223 (g)
    from apps.managed_hosting.extra_quota_counters import month_start
    # A draft created this month already counts toward `events_monthly`; one from an earlier month does not.
    limits.check_quota(locked.makerspace, "events", adding=1,
                       monthly_adding=0 if locked.created_at >= month_start() else 1)
    locked.status = Event.Status.PUBLISHED
    locked.version += 1
    locked.save(update_fields=["status", "version", "updated_at"] + (["registration_audience"] if fell_back else []))
    if publish_website:
        from .services_website import set_release_locked
        set_release_locked(locked, actor=actor, released=True, revision=website_revision)
    calendar_event_changed(locked)
    meta = {"old_status": Event.Status.DRAFT, "new_status": Event.Status.PUBLISHED}
    if fell_back:
        meta["audience_fallback"] = "members_to_accounts"
    services._audit(locked, actor, "event.published", locked, meta)
    without_room = venue["state"] == "blocked"
    if without_room:
        services._audit(locked, actor, "event.published_without_room", locked,
                        {"venue_reason": venue["reason"], "booking_id": venue["booking_id"]})
    services.notify_event_lifecycle(locked, "published")
    if not without_room:  # never silently charge a venue fee for a room the event does not hold
        from .venue_fees import on_event_published  # lane L6: confirming the event charges its venue fee
        on_event_published(locked, actor)
    return services._refresh(locked)


@event_write(permission="publish_schedule")
def cancel(event, *, actor, notify=True):
    services = _boundary()
    _lock_series_first(event.pk)
    locked = services._locked_event(event.pk)
    if locked.status != Event.Status.PUBLISHED:
        raise EventInvalidTransition(
            f"Cannot transition event from {locked.status} to {Event.Status.CANCELLED}."
        )
    locked.status = Event.Status.CANCELLED
    locked.version += 1
    locked.save(update_fields=["status", "version", "updated_at"])
    from .hackathons.admission_lifecycle import cancel_event_locked
    cancel_event_locked(event_id=locked.pk, actor=actor, locks=current_locks(locked.pk))
    from .contributions.admission_adapter import cancel_event_locked as cancel_contributions
    cancel_contributions(event=locked, actor=actor, locks=current_locks(locked.pk))
    from .credentials.workflow import revoke_locked
    from .models import EventRegistration
    for registration in EventRegistration.objects.select_for_update().filter(event=locked).order_by("pk"):
        revoke_locked(registration, actor=actor, reason="event_cancelled")
    survey = EventFeedbackSurvey.objects.select_for_update().filter(event=locked).first()
    certificates = list(EventAttendanceCertificate.objects.select_for_update().filter(
        event=locked, status=EventAttendanceCertificate.Status.ACTIVE,
    ))
    now = timezone.now()
    if survey is not None and survey.is_open:
        survey.is_open = False
        survey.closed_at = now
        survey.save(update_fields=["is_open", "closed_at", "updated_at"])
        services._audit(
            locked, actor, "event.feedback_survey_closed", survey,
            {"reason": "event_cancelled"},
        )
    for certificate in certificates:
        certificate.status = EventAttendanceCertificate.Status.REVOKED
        certificate.revoked_at = now
        certificate.revoked_by = actor
        certificate.revocation_reason = (
            EventAttendanceCertificate.RevocationReason.EVENT_CANCELLED
        )
        certificate.save(update_fields=[
            "status", "revoked_at", "revoked_by", "revocation_reason",
        ])
        services._audit(
            locked, actor, "event.certificate_revoked", certificate,
            {"reason": certificate.revocation_reason, "revision": certificate.revision},
        )
    calendar_event_changed(locked, now=now)
    services._audit(
        locked, actor, "event.cancelled", locked,
        {"old_status": Event.Status.PUBLISHED, "new_status": Event.Status.CANCELLED},
    )
    if notify:
        services.notify_event_lifecycle(locked, "cancelled")
    # Decision 216: the linked booking and loans are told, never cancelled (also for a series cancel).
    from .linked_change_notices import event_changed
    event_changed(locked, "cancelled")
    from .guest_pass_event_changes import schedule_cancelled  # audit M5: its guest passes end with it
    schedule_cancelled(locked)
    _cancel_open_charges_after_commit(locked, actor)
    from .programme_charges import close_for_cancelled_event  # hack-money G1: entry and team fees too
    close_for_cancelled_event(locked, actor)
    return services._refresh(locked)


def _cancel_open_charges_after_commit(event, actor, *, registration_ids=None):
    """An event that will not happen must not keep billing its attendees.

    PENDING charges are cancelled. A settled one is money that really arrived: it stays
    on the ledger and gets a refund case for the FULL amount (reason `event_cancelled`,
    owner decision 60) for staff to approve. Post-commit and one at a time, because
    cancelling expires any live provider checkout, and provider I/O must never run while
    the event row lock is held. `cancel_for_registration` swallows its own failures, so
    a provider outage never undoes the cancellation; the refund sweep rebuilds a case
    a failure left behind.

    With ``registration_ids`` the caller has just cancelled or rejected those rows
    itself: their settled charges are assessed under the refund policy
    (``registration_cancelled``), exactly as the direct call did before the write
    boundary moved this post-commit.
    """
    from apps.events.models import EventRegistration
    from apps.events.service_payments import cancel_for_registration
    from apps.payments.models import Payment
    from apps.events.orders_refunds import after_event_charges  # lane L6: ticket orders and their seats

    after_event_charges(event, actor, registration_ids=registration_ids)
    # Hack-money G10: a cancelled or rejected place closes its deposit (an event cancellation closes
    # them through `programme_charges.close_for_cancelled_event`).
    from apps.events.judging.deposits import close_deposits_after_commit
    close_deposits_after_commit(event, actor, registration_ids)
    single = registration_ids is not None
    registration_ids = registration_ids if single else list(
        EventRegistration.objects.filter(event=event).values_list("pk", flat=True)
    )
    pending = set(
        Payment.objects.filter(
            makerspace=event.makerspace,
            subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id__in=registration_ids,
            status=Payment.Status.PENDING,
        ).values_list("subject_id", flat=True)
    )
    reason_code = "registration_cancelled" if single else "event_cancelled"
    # A member who had already cancelled was assessed under the policy at the time;
    # only registrations still standing when the space cancels are owed in full.
    standing = EventRegistration.objects.filter(event=event)
    standing = standing.filter(pk__in=registration_ids) if single else standing.exclude(
        status__in=(EventRegistration.Status.CANCELLED, EventRegistration.Status.REJECTED),
    )
    paid = set(
        Payment.objects.filter(
            makerspace=event.makerspace,
            subject_type=Payment.SubjectType.EVENT_REGISTRATION,
            subject_id__in=standing.values("pk"),
            status__in=(Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE),
        ).values_list("subject_id", flat=True)
    )

    def cancel_all():
        for registration in EventRegistration.objects.filter(pk__in=pending | paid).select_related(
            "event__makerspace"
        ):
            with transaction.atomic():
                cancel_for_registration(registration, actor, reason_code=reason_code)

    if pending or paid:
        transaction.on_commit(cancel_all)


@event_write(permission="publish_schedule")
def complete(event, *, actor):
    from .hackathons.admission_lifecycle import close_event_locked
    close_event_locked(event=event, actor=actor, locks=current_locks(event.pk))
    from .contributions.admission_adapter import close_event_locked as close_contributions
    close_contributions(event=event, actor=actor, locks=current_locks(event.pk))
    return _transition(
        event, actor, Event.Status.PUBLISHED, Event.Status.COMPLETED, "event.completed"
    )
