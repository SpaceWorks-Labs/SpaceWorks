"""Payment edges; provider identifiers and financial amounts never enter staff chat."""

from apps.integrations.notifications_research import notify_family, safe_adapter
from .notification_projections import payment_subject


@safe_adapter
def notify_payment(payment, event, *, refund=None, requester_only=False):
    staff = payment_subject(payment, audience="staff")
    own = payment_subject(payment, audience="member", refund=refund)
    return notify_family(
        payment.makerspace, "payments", event, staff,
        data={"payment_id": payment.pk, "refund_id": refund.pk if refund else None},
        member_id=payment.member_id, requester_subject=own,
        requester_only=requester_only,
    )
