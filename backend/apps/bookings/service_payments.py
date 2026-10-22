"""Required booking ledger writes are atomic; optional online rails are best-effort."""

import logging

from django.db import IntegrityError, transaction

from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import MakerspacePaymentSettings, Payment
from apps.payments.refund_cancellation import cancel_or_hold
from apps.payments.services import create_checkout, create_payment

logger = logging.getLogger(__name__)


def create_for_confirmed_booking(booking, actor):
    space = booking.space
    makerspace = space.makerspace
    member = booking.member
    if (
        member is None
        or space.payment_amount <= 0
        or not charge_tracking_enabled(makerspace, "bookings")
    ):
        return None
    # The caller's atomic booking transaction must also commit its required debt.
    # Only the optional provider rail may fail after this local ledger write.
    payment = _get_or_create(booking, actor or member)
    try:
        if payment.status == Payment.Status.PENDING and online_payments_enabled(
            makerspace, "bookings"
        ):
            _schedule_checkout(payment)
    except Exception:
        logger.exception("booking_checkout_schedule_failed", extra={"payment_id": payment.pk})
    return payment


def _get_or_create(booking, created_by):
    lookup = {
        "makerspace": booking.space.makerspace,
        "subject_type": Payment.SubjectType.BOOKING,
        "subject_id": booking.pk,
    }
    existing = Payment.objects.filter(**lookup).first()
    if existing is not None:
        return existing
    currency = MakerspacePaymentSettings.for_makerspace(
        booking.space.makerspace
    ).default_currency
    try:
        with transaction.atomic():
            return create_payment(
                **lookup,
                member=booking.member,
                amount=booking.space.payment_amount,
                currency=currency,
                created_by=created_by,
                subject_label=booking.space.name,
                due_at=booking.starts_at,
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
