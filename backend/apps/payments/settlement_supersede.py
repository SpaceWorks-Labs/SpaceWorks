"""Close the offline decisions a charge no longer needs once it settles another way.

Payments audit 0.12.0 R-9/R-12: an open "I paid" claim, or a maker-checker proposal waiting for
its second person, used to outlive the charge. Staff then met a 409 `payment_terminal` on
confirm with the claim still sitting in the queue. Every terminal settlement (online capture,
offline receipt, waiver) now closes them, in the same transaction and under the Payment lock
the settling code already holds, and writes an audit row per item closed.

The claim being confirmed (or the proposal being confirmed) is the settlement itself, so its
caller names it with `keeping(...)` and it is left for its own finishing step.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.utils import timezone
from django.utils.translation import gettext_noop

from apps.audit import services as audit
from apps.payments.models import PaymentClaim, SettlementConfirmation

_KEEP = ContextVar("settlement_supersede_keep", default=((), ()))
NOTE = gettext_noop("This charge was settled another way, so the claim was closed.")


@contextmanager
def keeping(*, claim_id=None, confirmation_id=None):
    claims, confirmations = _KEEP.get()
    token = _KEEP.set((claims + ((claim_id,) if claim_id else ()),
                       confirmations + ((confirmation_id,) if confirmation_id else ())))
    try:
        yield
    finally:
        _KEEP.reset(token)


def supersede_open_settlements(payment, *, actor=None):
    """Reject every open claim and awaiting proposal of `payment` except the ones being confirmed."""
    keep_claims, keep_confirmations = _KEEP.get()
    now = timezone.now()
    for row in SettlementConfirmation.objects.select_for_update().filter(
            payment=payment, status=SettlementConfirmation.Status.AWAITING).exclude(pk__in=keep_confirmations):
        row.status, row.decided_at, row.decision_note = SettlementConfirmation.Status.REJECTED, now, NOTE
        row.save()
        audit.record(actor, "payment.settlement_superseded", makerspace=payment.makerspace, target=payment,
                     meta={"confirmation_id": row.pk, "payment_status": payment.status})
    for claim in PaymentClaim.objects.select_for_update().filter(
            payment=payment, status__in=PaymentClaim.OPEN_STATUSES).exclude(pk__in=keep_claims):
        claim.status, claim.decided_by, claim.decided_at = PaymentClaim.Status.REJECTED, actor, now
        claim.decision_note = NOTE
        claim.save(update_fields=["status", "decided_by", "decided_at", "decision_note"])
        audit.record(actor, "payment.paid_claim_superseded", makerspace=payment.makerspace, target=payment,
                     meta={"claim_id": claim.pk, "payment_status": payment.status})
