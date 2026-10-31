"""Required booking ledger writes are atomic; optional online rails are best-effort."""

import logging

from django.db import IntegrityError, transaction

from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import Payment
from apps.payments.refund_cancellation import cancel_or_hold
from apps.payments.services import create_checkout, create_payment

logger = logging.getLogger(__name__)


def booking_quote(booking, member=None):
    """Lane L15: per booking + per hour x booked time (rounded up), capped per day."""
    from apps.payments.pricing import quote

    return quote(booking.space.makerspace, "bookings", booking.space, member=member or booking.member,
                 params={"starts_at": booking.starts_at, "ends_at": booking.ends_at})


def create_for_confirmed_booking(booking, actor):
    space = booking.space
    makerspace = space.makerspace
    member = booking.member
    if member is None or not charge_tracking_enabled(makerspace, "bookings"):
        return None
    existing = Payment.objects.filter(makerspace=makerspace, subject_type=Payment.SubjectType.BOOKING,
                                      subject_id=booking.pk).first()
    priced = None
    if existing is None:
        priced = booking_quote(booking)
        if priced.total <= 0:
            if priced.lines:
                from apps.payments.pricing.charging import record_free
                record_free(priced, actor=actor or member, makerspace=makerspace, target=booking,
                            subject_type=Payment.SubjectType.BOOKING, subject_id=booking.pk)
            return None
    # The caller's atomic booking transaction must also commit its required debt.
    # Only the optional provider rail may fail after this local ledger write.
    payment = _get_or_create(booking, actor or member, priced)
    try:
        if payment.status == Payment.Status.PENDING and online_payments_enabled(
            makerspace, "bookings"
        ):
            _schedule_checkout(payment)
    except Exception:
        logger.exception("booking_checkout_schedule_failed", extra={"payment_id": payment.pk})
    return payment


def _get_or_create(booking, created_by, priced=None):
    from apps.payments.pricing.charging import raise_priced

    lookup = {
        "makerspace": booking.space.makerspace,
        "subject_type": Payment.SubjectType.BOOKING,
        "subject_id": booking.pk,
    }
    existing = Payment.objects.filter(**lookup).first()
    if existing is not None:
        return existing
    priced = priced or booking_quote(booking)
    try:
        with transaction.atomic():
            return raise_priced(
                priced, **lookup, member=booking.member, created_by=created_by, target=booking,
                subject_label=booking.space.name, due_at=booking.starts_at, create=create_payment,
            )
    except IntegrityError:
        return Payment.objects.get(**lookup)


def _schedule_checkout(payment):
    def create_safely():
        try:
            create_checkout(payment)
        except Exception:
            logger.exception("booking_checkout_failed", extra={"payment_id": payment.pk})

    transaction.on_commit(create_safely)


def cancel_for_booking(booking, actor, by_staff=False):
    # Reconciliation already isolates provider failures. Local update/audit failures
    # must reach cancel_booking's atomic boundary and roll back the booking too (BK-0):
    # a paid booking's refund case commits or rolls back with the cancellation itself.
    return cancel_or_hold(
        makerspace=booking.space.makerspace,
        subject_type=Payment.SubjectType.BOOKING,
        subject_id=booking.pk,
        actor=actor,
        reason_code="staff_cancelled" if by_staff else "booking_cancelled",
        cancelled_at=booking.cancelled_at,
    )
