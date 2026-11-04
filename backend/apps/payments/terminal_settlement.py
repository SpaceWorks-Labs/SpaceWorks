"""Narrow exception for money received after a charge was waived."""

from django.db import connection
from django.utils import timezone

from apps.audit import services as audit
from apps.audit.models import AuditLog
from apps.payments.models import Payment
from apps.payments.admission_settlement import resume_admission_after_settlement


def handle_stripe_paid_after_terminal(payment, *, event_id, intent_id=None):
    """Correct or flag a late Stripe payment after staff reconciliation."""
    prior_status = payment.status
    if prior_status == Payment.Status.WAIVED:
        promote_waived_to_paid_online(payment, intent_id=intent_id)

    audit.record(
        None,
        "payment.paid_after_terminal",
        makerspace=payment.makerspace,
        target=payment,
        meta={
            "stripe_event_id": event_id,
            "prior_status": prior_status,
            "resolved_status": payment.status,
        },
    )
    if prior_status == Payment.Status.PAID_OFFLINE:
        audit.record(
            None,
            "payment.double_paid_refund_required",
            makerspace=payment.makerspace,
            target=payment,
            meta={"stripe_event_id": event_id, "prior_status": prior_status},
        )
    return payment


def handle_razorpay_paid_after_terminal(
    payment, *, event_id, payment_id, amount_minor=0, currency="",
):
    """Correct or flag a late Razorpay payment after staff reconciliation."""
    prior_status = payment.status
    if prior_status == Payment.Status.WAIVED:
        promote_waived_to_paid_online(payment, external_payment_id=payment_id)

    audit.record(
        None,
        "payment.paid_after_terminal",
        makerspace=payment.makerspace,
        target=payment,
        meta={
            "provider": "razorpay",
            "event_id": event_id,
            "prior_status": prior_status,
            "resolved_status": payment.status,
        },
    )
    # The Payment lock serializes this audit check across distinct webhook event ids.
    # One capture can arrive as both order.paid and payment.captured. Only a DIFFERENT
    # capture needs a dashboard refund; never change the settled row or its Refunds.
    if (
        prior_status != Payment.Status.WAIVED
        and payment_id and payment_id != payment.external_payment_id
        and not AuditLog.objects.filter(
            makerspace_id=payment.makerspace_id,
            target_type=payment._meta.label_lower, target_id=str(payment.pk),
            action="payment.double_paid_refund_required",
            meta__provider="razorpay", meta__provider_payment_id=payment_id,
        ).exists()
    ):
        audit.record(
            None,
            "payment.double_paid_refund_required",
            makerspace=payment.makerspace,
            target=payment,
            meta={
                "provider": "razorpay",
                "event_id": event_id,
                "prior_status": prior_status,
                "provider_payment_id": payment_id,
                "amount_minor": amount_minor,
                "currency": currency,
            },
        )
    return payment


def promote_waived_to_paid_online(payment, *, intent_id=None, external_payment_id=None):
    """Correct a locked waived row after the provider confirms real payment.

    The database GUC is transaction-scoped, and the trigger accepts only the exact
    ``waived`` to ``paid_online`` transition with an unchanged amount. Callers must hold
    the payment row lock inside an atomic block.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL app.allow_waived_online_settlement = 'on'")

    updates = {
        "status": Payment.Status.PAID_ONLINE,
        "updated_at": timezone.now(),
    }
    if intent_id:
        updates["stripe_payment_intent_id"] = intent_id
    if external_payment_id:
        updates["external_payment_id"] = external_payment_id
    changed = Payment.objects.filter(
        pk=payment.pk, status=Payment.Status.WAIVED
    ).update(**updates)
    if changed != 1:
        raise RuntimeError("The waived payment could not be settled.")
    payment.status = Payment.Status.PAID_ONLINE
    payment.updated_at = updates["updated_at"]
    if intent_id:
        payment.stripe_payment_intent_id = intent_id
    if external_payment_id:
        payment.external_payment_id = external_payment_id
    from apps.payments.documents import issue_receipt
    issue_receipt(payment)
    from apps.payments.notifications import notify_payment
    notify_payment(payment, "payment_received")
    resume_admission_after_settlement(payment)
    return payment
