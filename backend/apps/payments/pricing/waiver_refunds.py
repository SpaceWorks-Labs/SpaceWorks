"""A waived loan fee that was already PAID opens a staff-approved refund case (A14, #59).

Nothing here moves money: the case records what the space owes back (the refundable
balance) and waits for a staff decision in the refund queue, exactly like a policy case.
Lock order matches `services_refund_cases`: the caller holds the loan row, then Payment,
then RefundCase.
"""

from apps.payments.models import RefundCase
from apps.payments.refund_policy import area_for, refundable_balance
from apps.payments.services_refund_cases import _active, _lock_payment, _notify, record_case

SETTLED = ("paid_online", "paid_offline")


def open_waiver_case(payment, waiver, actor):
    locked = _lock_payment(payment.pk)
    if locked.status not in SETTLED:
        return None
    balance = refundable_balance(locked)
    if balance <= 0:
        return None
    snapshot = {"rule": "fee_waived", "waiver_id": waiver.pk, "balance": str(balance),
                "currency": locked.currency, "paid": str(locked.amount)}
    case = _active(locked)
    has_due = RefundCase.objects.filter(payment=locked, kind=RefundCase.Kind.DUE).exists()
    if case is not None:
        if not has_due and case.kind == RefundCase.Kind.REQUEST:
            case.kind, case.reason_code, case.due_amount, case.policy_snapshot = (
                RefundCase.Kind.DUE, RefundCase.ReasonCode.FEE_WAIVED, balance, snapshot)
            case.save(update_fields=["kind", "reason_code", "due_amount", "policy_snapshot", "updated_at"])
            record_case(actor, "payment.refund_case_updated", case, due_amount=str(balance),
                        reason_code=case.reason_code)
        return case
    # A charge is assessed as DUE at most once; a later waiver on a charge whose due case
    # was already decided opens a staff request case instead, still awaiting approval.
    kind = RefundCase.Kind.REQUEST if has_due else RefundCase.Kind.DUE
    case = RefundCase.objects.create(
        payment=locked, kind=kind, area=area_for(locked), reason_code=RefundCase.ReasonCode.FEE_WAIVED,
        due_amount=balance, policy_snapshot=snapshot,
    )
    record_case(actor, "payment.refund_case_opened", case, due_amount=str(balance),
                reason_code=case.reason_code)
    _notify(case, "refund_due_opened")
    return case
