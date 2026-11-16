"""X21 (L4): an approved membership refund ends the term it paid for.

Default on; staff keep the membership by ticking `keep_membership` on the approval. The
term is ended AFTER the approval commits, in its own transaction, so the term lock is
never taken while the Payment/RefundCase locks are held (the cancellation path takes
term then payment). An UPCOMING term that was paid early is cancelled the same way.
Ending goes through `cancel_term` without opening another refund case -- this approval
already decides the money -- and voids a still-pending renewal. The member's card stops
verifying because it reads the current term. Audited as `payment.refund_case_term_ended`.
Money moves only through the approved `RefundCase`, never here.
"""
import logging

from django.db import transaction

from apps.payments.models import RefundCase

logger = logging.getLogger(__name__)


def end_term_after_commit(case, payment, actor):
    if case.area != RefundCase.Area.MEMBERSHIP:
        return
    from apps.payments.refund_policy_membership import term_for_payment
    term = term_for_payment(payment)
    if term is None or term.status != "active":
        return

    def end():
        from apps.audit import services as audit
        from apps.makerspaces.membership_plan_services import cancel_term
        try:
            with transaction.atomic():
                ended = cancel_term(actor, term, reason="Membership refund approved", hold_charges=False)
                audit.record(actor, "payment.refund_case_term_ended", makerspace=payment.makerspace,
                             target=payment, meta={"case_id": case.pk, "payment_id": payment.pk,
                                                   "term_id": ended.pk})
        except Exception:  # noqa: BLE001 - the approved refund stands; staff can cancel the term by hand
            logger.exception("refund_case_term_end_failed", extra={"case_id": case.pk, "term_id": term.pk})

    transaction.on_commit(end)
