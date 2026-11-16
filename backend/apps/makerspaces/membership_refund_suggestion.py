"""X20: the refund the membership policy would suggest for a charge, if cancelled now.

Pure arithmetic over the existing assessment (`payments.refund_policy.assess`, owner
decision 68) with the membership-cancelled reason: it opens no case and moves nothing.
Shown to the member before they ask and to staff deciding the case; staff still choose
the amount on approval.
"""
from django.utils import timezone

from apps.payments.models import Payment, RefundCase

MEMBERSHIP_SUBJECTS = (Payment.SubjectType.MEMBERSHIP_TERM, Payment.SubjectType.MEMBERSHIP_TERM_START,
                       Payment.SubjectType.MEMBERSHIP_REQUEST,
                       Payment.SubjectType.MAKERSPACE_MEMBERSHIP)


def suggestion(payment, *, now=None):
    from apps.payments.refund_policy import assess
    if payment.subject_type not in MEMBERSHIP_SUBJECTS:
        return {"applies": False, "suggested_amount": None, "currency": payment.currency, "band": "", "rule": ""}
    if payment.status not in (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE):
        return {"applies": False, "suggested_amount": None, "currency": payment.currency, "band": "",
                "rule": "not_settled"}
    due, snapshot = assess(payment, reason_code=RefundCase.ReasonCode.MEMBERSHIP_CANCELLED,
                           cancelled_at=now or timezone.now())
    policy = snapshot.get("rule") == "policy"
    return {"applies": policy, "suggested_amount": due if policy else None, "currency": payment.currency,
            "band": snapshot.get("band", ""), "rule": snapshot.get("rule", "")}
