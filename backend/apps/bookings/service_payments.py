"""Required booking ledger writes are atomic; optional online rails are best-effort."""

import logging

from django.db import IntegrityError, transaction

from apps.payments.availability import charge_tracking_enabled, online_payments_enabled
from apps.payments.models import Payment
from apps.payments.refund_cancellation import cancel_or_hold
from apps.payments.services import create_checkout, create_payment

logger = logging.getLogger(__name__)


def booking_quote(booking, member=None, *, exempt=False, fresh=False, organization=None):
    """Lane L15: per booking + per hour x booked time (rounded up), capped per day.

    Decision 221(d): the member's plan hours come off the billed time first. A saved booking
    keeps the hours its own ledger row holds; `fresh` re-reads the member's balance (creation),
    `exempt` skips it (staff-made event-venue replacement)."""
    from apps.payments.pricing import quote

    # B13: an organization booking draws from the organization's hours bank, never the contact's plan.
    from .organization_hours import organization_of
    organization = organization or organization_of(booking)
    return quote(booking.space.makerspace, "bookings", booking.space, member=member or booking.member,
                 params={"starts_at": booking.starts_at, "ends_at": booking.ends_at,
                         "booking": None if fresh else booking, "included_exempt": exempt or organization is not None,
                         "organization": organization})


def requested_snapshot(booking, *, priced=None, exempt=False, organization=None):
    """#159: the quote frozen on a booking that waits for approval ({} when nothing is tracked).

    `priced` is a staff-confirmed quote verified under the same lock (decision 216)."""
    if booking.member is None or not charge_tracking_enabled(booking.space.makerspace, "bookings"):
        return {}
    return (priced if priced is not None else booking_quote(booking, exempt=exempt, organization=organization)
            ).to_snapshot(frozen_at="request")


def charged_quote(booking, actor, *, approval=False):
    """The requested price when one was frozen; else today's quote (audited on approval)."""
    from apps.payments.pricing.quotes import FrozenQuote

    if booking.pricing_snapshot:
        return FrozenQuote(booking.pricing_snapshot)
    if approval:
        from apps.audit import services as audit
        audit.record(actor, "booking.price_quoted_at_approval", makerspace=booking.space.makerspace,
                     target=booking, meta={"booking_id": booking.pk})
    return booking_quote(booking)


def create_for_confirmed_booking(booking, actor, *, approval=False, priced=None):
    """`priced`: a staff-confirmed quote verified in the creating transaction (decision 216)."""
    space = booking.space
    makerspace = space.makerspace
    member = booking.member
    if member is None or not charge_tracking_enabled(makerspace, "bookings"):
        return None
    existing = Payment.objects.filter(makerspace=makerspace, subject_type=Payment.SubjectType.BOOKING,
                                      subject_id=booking.pk).first()
    if existing is not None:
        priced = None
    else:
        if priced is None:
            priced = charged_quote(booking, actor or member, approval=approval)
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
                subject_label=booking.space.name, due_at=booking.starts_at, create=create_payment, quota_gate=True,
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
