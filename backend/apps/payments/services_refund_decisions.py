"""Staff decisions on a refund case. Approval is the ONLY place a case becomes money.

Approve, under Payment -> RefundCase locks:
* online charge -> a PENDING `Refund` through `open_refund_locked`; the provider call
  runs after commit through the existing send/settle path. A refused refund moves the
  case to APPROVAL_FAILED so staff can retry or decline (R2).
* offline charge -> `record_offline_refund`, which demands a receipt (method,
  reference, date) because the money is handed back in person (R3).
Deciding needs subject authority for the charge's domain; recording cash also needs
RECORD_PAYMENT. With the payments rail removed an online case can only be declined (R4).
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.payments.exceptions_refunds import RefundCaseConflict, RefundNotAllowed
from apps.payments.models import Payment, RefundCase
from apps.payments.reconciliation_authority import _require_subject_authority, may_record_cash
from apps.payments.refund_policy import precision_ok, refundable_balance
from apps.payments.services_refund_cases import _lock_payment, _notify, record_case


def _lock_case(case, actor):
    payment = _lock_payment(case.payment_id)
    locked = RefundCase.objects.select_for_update(of=("self",)).get(pk=case.pk)
    locked.payment = payment
    _require_subject_authority(actor, [payment])
    if locked.status not in RefundCase.ACTIVE_STATUSES:
        raise RefundCaseConflict("This refund case is already closed.", "refund_case_closed", status=locked.status)
    return payment, locked


def _amount(raw, case, payment, balance):
    if raw in (None, ""):
        raw = min(case.due_amount, balance)
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, TypeError, ValueError):
        raise RefundNotAllowed("Refund amount is invalid.", "refund_amount_invalid")
    if amount <= 0 or not precision_ok(amount, payment.currency):
        raise RefundNotAllowed("Refund amount is invalid for this currency.", "refund_amount_invalid")
    if amount > balance:
        raise RefundCaseConflict("Refund exceeds the refundable balance.", "refund_exceeds_balance",
                                 balance=str(balance))
    return amount.quantize(Decimal("0.01"))


def approve_case(case, *, actor, amount=None, reason="", note="", receipt=None, keep_membership=False):
    exhausted = False
    with transaction.atomic():
        payment, locked = _lock_case(case, actor)
        balance = refundable_balance(payment)
        if balance <= 0:
            # Refunded outside the case already: nothing left to approve (R7).
            locked.status, locked.decided_at = RefundCase.Status.VOID, timezone.now()
            locked.save(update_fields=["status", "decided_at", "updated_at"])
            record_case(actor, "payment.refund_case_voided", locked, reason="balance_exhausted")
            exhausted = True
        else:
            refund = _approve_locked(payment, locked, actor=actor, amount=_amount(amount, locked, payment, balance),
                                     reason=reason or "Refund approved", note=note, receipt=receipt)
    if exhausted:
        raise RefundCaseConflict("Nothing is left to refund on this charge.", "refund_exceeds_balance",
                                 balance="0.00")
    if refund.status == refund.Status.PENDING and payment.status == Payment.Status.PAID_ONLINE:
        _send_after_commit(refund, actor)
    if not keep_membership:
        from apps.payments.refund_membership_term import end_term_after_commit
        end_term_after_commit(locked, payment, actor)
    return RefundCase.objects.select_related("payment__makerspace", "refund").get(pk=locked.pk)


def _approve_locked(payment, case, *, actor, amount, reason, note, receipt):
    if payment.status == Payment.Status.PAID_ONLINE:
        from apps.separability.tombstones import app_is_tombstoned
        if app_is_tombstoned("payments_rail"):
            raise RefundCaseConflict("Online refunds are not available on this deployment; decline instead.",
                                     "refund_rail_unavailable")
    elif not may_record_cash(actor, payment):
        raise PermissionDenied("Recording a cash refund requires record_payment.")
    elif not receipt:
        raise RefundNotAllowed("An offline refund needs a receipt: method, reference and date.",
                               "refund_receipt_required")
    # Mark the decision BEFORE the refund exists: the refund path voids every still-active
    # case once the balance reaches zero, and this one is not still active.
    case.status, case.approved_amount, case.decision_note = RefundCase.Status.APPROVED, amount, (note or "")[:500]
    case.decided_by, case.decided_at = actor, timezone.now()
    case.save(update_fields=["status", "approved_amount", "decision_note", "decided_by", "decided_at", "updated_at"])
    if payment.status == Payment.Status.PAID_ONLINE:
        from apps.payments.services_refunds import open_refund_locked
        refund = open_refund_locked(payment, amount=amount, reason=reason, actor=actor)
    else:
        from apps.payments.services_refunds_offline import record_offline_refund
        refund = record_offline_refund(payment, amount=amount, reason=reason, receipt=receipt, actor=actor)
    case.refund = refund
    case.save(update_fields=["refund", "updated_at"])
    record_case(actor, "payment.refund_case_approved", case, refund_id=refund.pk, amount=str(amount))
    _notify(case, "refund_request_approved")
    return refund


def _send_after_commit(refund, actor):
    """Provider I/O outside every lock. A refusal is settled FAILED, which moves the case
    to APPROVAL_FAILED inside `settle_refund` -- the same place a failing webhook lands."""
    def send():
        from apps.payments.services_refunds import dispatch_refund
        dispatch_refund(refund, actor=actor)

    transaction.on_commit(send)


@transaction.atomic
def decline_case(case, *, actor, note):
    payment, locked = _lock_case(case, actor)
    locked.status, locked.decision_note = RefundCase.Status.DECLINED, (note or "")[:500]
    locked.decided_by, locked.decided_at = actor, timezone.now()
    locked.save(update_fields=["status", "decision_note", "decided_by", "decided_at", "updated_at"])
    record_case(actor, "payment.refund_case_declined", locked)
    _notify(locked, "refund_request_declined")
    return locked
