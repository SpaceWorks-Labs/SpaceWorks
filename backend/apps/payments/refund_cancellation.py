"""One seam for "the thing this charge paid for will not happen".

`cancel_or_hold` wraps `reconciliation.cancel_pending`: a PENDING charge is voided as
before; a charge that was already PAID (online or offline) stays exactly as it is and
instead gets a refund case for whatever the policy says is owed. Money is never sent
back here -- a staff approval does that.
"""

from django.db import transaction

from apps.payments.models import Payment
from apps.payments.reconciliation import cancel_pending


@transaction.atomic
def cancel_or_hold(*, makerspace, subject_type, subject_id, actor, reason_code, cancelled_at=None):
    payment = cancel_pending(makerspace=makerspace, subject_type=subject_type, subject_id=subject_id, actor=actor)
    if payment is None or payment.status not in (Payment.Status.PAID_ONLINE, Payment.Status.PAID_OFFLINE):
        return payment
    from apps.payments.services_refund_cases import open_due_case
    open_due_case(payment, reason_code=reason_code, actor=actor, cancelled_at=cancelled_at)
    return payment
