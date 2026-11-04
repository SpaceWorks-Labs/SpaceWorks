"""Giving money back (#59): ONLY through a staff-approved refund case in area `donations`.

Staff open a case on a received gift or sponsor payment; deciding it (approve with a provider
refund or an offline receipt, or decline) is the ordinary refund-case queue, where approval
needs record_payment. The direct staff refund routes refuse these subjects
(`refund_via_case_only`), so no gift is returned without that decision.
"""

from django.db import transaction

from apps.payments.exceptions_refunds import RefundCaseConflict, RefundNotAllowed

CASE_ONLY_SUBJECTS = ("donation", "sponsorship")


def refuse_direct_refund(payment):
    if payment is not None and payment.subject_type in CASE_ONLY_SUBJECTS:
        raise RefundNotAllowed("Gifts and sponsor payments are returned through a refund case that staff approve.",
                               "refund_via_case_only")


@transaction.atomic
def open_return_case(payment, *, actor, reason=""):
    from apps.payments.models import Payment, RefundCase
    from apps.payments.refund_policy import refundable_balance
    from apps.payments.services_refund_cases import _active, _lock_payment, _notify, record_case

    locked = _lock_payment(payment.pk)
    if locked.subject_type not in CASE_ONLY_SUBJECTS:
        raise RefundNotAllowed("Not a gift or sponsor payment.", "refund_request_not_allowed")
    if locked.status not in (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE):
        raise RefundNotAllowed("Only a received payment can be returned.", "refund_not_settled")
    if refundable_balance(locked) <= 0:
        raise RefundNotAllowed("This payment has already been returned in full.", "refund_exceeds_balance")
    existing = _active(locked)
    if existing is not None:
        raise RefundCaseConflict("A refund case is already open for this payment.", "refund_request_exists",
                                 case_id=existing.pk)
    case = RefundCase.objects.create(
        payment=locked, kind=RefundCase.Kind.REQUEST, area=RefundCase.Area.DONATIONS,
        reason_code=RefundCase.ReasonCode.DONATION_RETURNED, member_reason=(reason or "").strip()[:500],
        requested_by=actor, due_amount=refundable_balance(locked))
    record_case(actor, "payment.refund_case_opened", case, reason_code=case.reason_code)
    from apps.audit import services as audit
    audit.record(actor, "donation.return_case_opened", makerspace=locked.makerspace, target=locked,
                 meta={"case_id": case.pk, "payment_id": locked.pk, "subject_type": locked.subject_type})
    _notify(case, "refund_request_received")
    return case
