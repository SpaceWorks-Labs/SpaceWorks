"""Parity C18: approving a refund on an event charge may also cancel the tickets it paid for.

The refund itself is untouched: the amount, the receipt and the provider call are exactly what the
case approval already does (sub-grid amounts stay `RefundNotAllowed`). Cancelling runs AFTER the
approval commits and outside every Payment lock, because it takes the event lock and may promote
the waitlist. A failure here never undoes the refund; it is audited so staff can cancel by hand.
Behind `events.refund_cancels_tickets`; the ledger stays core and works with the switch off.
"""

import logging

from django.db import transaction

from apps.payments.exceptions_refunds import RefundNotAllowed
from apps.payments.models import Payment
from apps.payments.services_refund_cases import record_case

logger = logging.getLogger(__name__)
EVENT_SUBJECTS = (Payment.SubjectType.EVENT_ORDER, Payment.SubjectType.EVENT_REGISTRATION)


def require_cancel_tickets_allowed(case):
    """Refuse before anything is locked: switch off, or the charge is not an event ticket."""
    from apps.makerspaces.platform import feature_enabled
    payment = case.payment
    if not feature_enabled(payment.makerspace, "events.refund_cancels_tickets"):
        raise RefundNotAllowed("Cancelling tickets with a refund is turned off for this makerspace.",
                               "refund_cancel_tickets_unavailable")
    if payment.subject_type not in EVENT_SUBJECTS:
        raise RefundNotAllowed("Only a refund on an event ticket charge can cancel tickets.",
                               "refund_cancel_tickets_not_event")


def cancel_tickets_after_commit(case, payment, actor):
    def run():
        from apps.events.orders_cancel import cancel_tickets_for_refund
        try:
            cancelled = cancel_tickets_for_refund(payment, actor=actor)
        except Exception:
            logger.error("refund_cancel_tickets_failed", extra={"case_id": case.pk, "payment_id": payment.pk})
            record_case(actor, "payment.refund_case_tickets_cancel_failed", case)
            return
        record_case(actor, "payment.refund_case_tickets_cancelled", case, cancelled=len(cancelled))

    transaction.on_commit(run)
