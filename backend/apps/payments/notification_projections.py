"""Reviewed payment values shared by email and addressed channel adapters.

Keep this module independent of the optional notifications app.
"""
from apps.integrations.email_templates_registry_helpers import bag
from apps.makerspaces.local_time import to_local


def payment_subject(payment, *, audience, refund=None):
    staff = {"id": payment.pk, "status": str(payment.status or "")[:160]}
    if audience == "staff":
        return bag(**staff)
    return bag(**staff, amount=str(refund.amount if refund else payment.amount)[:32],
        currency=str(payment.currency or "")[:8],
        due_date=to_local(payment.makerspace, payment.due_at).date().isoformat() if payment.due_at else "")
