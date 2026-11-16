"""Shared retry and immutable business-state assertions for document mail tests."""
from datetime import timedelta

from django.utils import timezone

from apps.audit.models import AuditLog
from apps.integrations.dispatch_delivery import _deliver
from apps.integrations.models import EmailLog
from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_delivery import send
from apps.payments.models import Payment, PaymentDocument


def retry_mail(path, envelope):
    if path == "direct":
        return _deliver(EmailLog.objects.filter(event="document_issued").latest("pk"))
    delivery = envelope.deliveries.get(channel="email")
    NotificationDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    send(delivery.pk)
    return EmailLog.objects.filter(event="document_issued").latest("pk")


def document_ledger_snapshot(document):
    return (
        Payment.objects.values("pk", "makerspace_id", "member_id", "amount", "currency", "status").get(pk=document.payment_id),
        PaymentDocument.objects.values("pk", "payment_id", "makerspace_id", "number", "kind", "amount", "currency").get(pk=document.pk),
        list(AuditLog.objects.filter(makerspace_id=document.makerspace_id).exclude(
            action__startswith="notification.").order_by("pk").values()),
    )


def intent_state(envelope):
    from apps.integrations.document_email_state import decide, envelope_identity
    return decide(**envelope_identity(envelope), event="inspect").intent
