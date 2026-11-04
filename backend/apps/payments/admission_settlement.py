"""Resume paid admissions after releasing the ledger's payment lock.

Admission services lock the makerspace, request, then payment. A settlement already
owns the payment lock, so calling admission inline could invert that lock order.
Post-commit failure never rolls back money received; the admission sweep retries it.
"""

import logging

from django.db import transaction

from apps.payments.models import Payment

logger = logging.getLogger(__name__)


def resume_admission_after_settlement(payment):
    if payment.subject_type == Payment.SubjectType.EVENT_ORDER:
        _resume_event_order(payment)
        return
    if payment.subject_type in Payment.ACCOUNTLESS_SUBJECT_TYPES:
        from apps.payments.donations.settlement import after_settlement  # lane L18

        after_settlement(payment)
        return
    if payment.subject_type != Payment.SubjectType.MEMBERSHIP_REQUEST or payment.status not in {
        Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE, Payment.Status.WAIVED,
    }:
        return
    payment_id = payment.pk

    def resume():
        try:
            from apps.makerspaces.membership_admission_payments import resume_after_payment

            resume_after_payment(payment_id)
        except Exception as exc:
            logger.warning("membership_admission_resume_failed", extra={
                "payment_id": payment_id, "failure_type": type(exc).__name__,
            })

    transaction.on_commit(resume)


def _resume_event_order(payment):
    """Lane L6: a paid ticket order seats its attendees after the payment lock is released."""
    if payment.status not in {Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE, Payment.Status.WAIVED}:
        return
    order_id = payment.subject_id

    def resume():
        try:
            from apps.events.orders_settlement import settle_paid_order

            settle_paid_order(order_id)
        except Exception as exc:
            logger.warning("event_order_settlement_failed", extra={
                "order_id": order_id, "failure_type": type(exc).__name__,
            })

    transaction.on_commit(resume)
