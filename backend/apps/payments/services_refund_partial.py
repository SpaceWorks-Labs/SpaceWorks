"""An explicit amount owed back on a settled charge that covers several things (lane L6).

`open_due_case` assesses a WHOLE charge once. A ticket order or a series pass is one
charge for many seats or occasions, so one seat cancelled, one occurrence cancelled or
one cheaper ticket owes back only its share, and it may happen more than once. This adds
that share to the charge's refund entitlement -- never money:

* an active case (open, or approval failed) grows by the share, in place (R1);
* otherwise, if the charge never had a policy assessment, a `due` case opens;
* otherwise a fresh case opens for staff (the one-due-per-payment rule stands).

Every amount is clamped to the refundable balance and rounded down to the currency.
Staff approve or decline exactly as for any case.
"""

from decimal import Decimal

from django.db import transaction

from apps.payments.models import RefundCase
from apps.payments.refund_policy import area_for, refundable_balance, round_down
from apps.payments.services_refund_cases import SETTLED, _active, _lock_payment, _notify, record_case


@transaction.atomic
def add_due_share(payment, *, amount, reason_code, actor, snapshot=None):
    """Grow (or open) the refund entitlement on `payment` by `amount`. Returns the case or None."""
    locked = _lock_payment(payment.pk)
    if locked.status not in SETTLED:
        return None
    owed = round_down(min(Decimal(amount), refundable_balance(locked)), locked.currency)
    if owed <= 0:
        return None
    facts = {"rule": "explicit_share", "share": str(owed), "reason_code": reason_code, **(snapshot or {})}
    case = _active(locked)
    if case is not None:
        total = round_down(min(case.due_amount + owed, refundable_balance(locked)), locked.currency)
        shares = list((case.policy_snapshot or {}).get("shares", []))
        case.due_amount = total
        case.policy_snapshot = {**(case.policy_snapshot or {}), "shares": [*shares, facts]}
        case.save(update_fields=["due_amount", "policy_snapshot", "updated_at"])
        record_case(actor, "payment.refund_case_updated", case, due_amount=str(total), reason_code=reason_code)
    else:
        kind = (RefundCase.Kind.REQUEST if RefundCase.objects.filter(payment=locked, kind=RefundCase.Kind.DUE).exists()
                else RefundCase.Kind.DUE)
        case = RefundCase.objects.create(payment=locked, kind=kind, area=area_for(locked), reason_code=reason_code,
                                         due_amount=owed, policy_snapshot={"shares": [facts]})
        record_case(actor, "payment.refund_case_opened", case, due_amount=str(owed), reason_code=reason_code)
    _notify(case, "refund_due_opened")
    return case
