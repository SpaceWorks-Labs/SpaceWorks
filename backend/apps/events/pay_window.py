"""The 24-hour pay window (parity E-B5, C22) for approved, promoted and re-accepted paid places.

Opening it stamps `EventRegistration.pay_by` beside the pending charge the place already owes; nothing about the
charge changes. A sweep (a pass of `reminders_payments.sweep_order_checkouts_task`, so there is no new beat
task) releases a place whose window ran out while the charge is still PENDING, through the ordinary
`cancel_registration` system path: that voids the unpaid charge via the payments services (the ledger row stays,
a settled one would get a refund case instead) and offers the freed place to the next waitlisted person.
Money in flight always wins: a charge that settled meanwhile just clears the window. Off means removed: nothing
opens, and a running window is simply ignored.
"""
from datetime import timedelta

from django.utils import timezone

from apps.audit import services as audit
from apps.makerspaces.platform import feature_enabled
from apps.payments.models import Payment

from .models import Event, EventRegistration
from .services_write_boundary import event_write

FEATURE = "events.pay_window"
WINDOW = timedelta(hours=24)


def open_for(registration, payment, actor):
    """Start the window for a place that owes a pending charge. Returns the deadline or None."""
    event = registration.event
    if payment is None or payment.status != Payment.Status.PENDING or not feature_enabled(event.makerspace, FEATURE):
        return None
    registration.pay_by = timezone.now() + WINDOW
    registration.save(update_fields=["pay_by"])
    audit.record(actor, "event.registration.pay_window_opened", makerspace=event.makerspace, target=registration,
                 meta={"registration_id": registration.pk})
    from .notices_pay_window import pay_window_notice
    pay_window_notice(registration, "pay_window_opened")
    return registration.pay_by


def _pending_charge(registration):
    return Payment.objects.select_for_update().filter(
        makerspace=registration.event.makerspace, subject_type=Payment.SubjectType.EVENT_REGISTRATION,
        subject_id=registration.pk, status=Payment.Status.PENDING).first()


def due(limit):
    from apps.makerspaces.scheduled_scope import live_space_ids
    return list(EventRegistration.objects.filter(
        pay_by__lte=timezone.now(), status=EventRegistration.Status.REGISTERED,
        event__makerspace_id__in=live_space_ids(FEATURE),
    ).order_by("pay_by").values_list("pk", flat=True)[:limit])


def expire(registration_id):
    row = EventRegistration.objects.select_related("event").get(pk=registration_id)
    return _expire(row.event, registration_id=registration_id, actor=None)


@event_write
def _expire(event, *, registration_id, actor):
    from .registration_locks import _lock_registration
    from .services_registration_state import cancel_registration
    locked = _lock_registration(event, registration_id)
    if (locked.pay_by is None or locked.pay_by > timezone.now()
            or locked.status != EventRegistration.Status.REGISTERED or event.status != Event.Status.PUBLISHED):
        return False
    if _pending_charge(locked) is None:  # paid (or never charged) while the sweep was queued: nothing to release
        locked.pay_by = None
        locked.save(update_fields=["pay_by"])
        return False
    cancel_registration(locked, actor=actor)
    locked.refresh_from_db()
    locked.pay_by = None
    locked.save(update_fields=["pay_by"])
    audit.record(actor, "event.registration.pay_window_expired", makerspace=event.makerspace, target=locked,
                 meta={"registration_id": locked.pk})
    from .notices_pay_window import pay_window_notice
    pay_window_notice(locked, "pay_window_expired")
    return True
