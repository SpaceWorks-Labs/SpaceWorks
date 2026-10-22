"""Verified opaque message identity -> exact tenant log -> monotonic observation."""

import hashlib

from django.db import transaction

from apps.accounts import rbac
from apps.audit import services as audit
from apps.integrations.models_email import EmailLog, EmailProviderWebhookReceipt
from apps.integrations.models_suppression import EmailSuppression
from apps.tenant_migration.gate_runtime import tenant_write


def observe(space, provider, event):
    if event.status is None:
        return True
    # Anymail Mailgun IDs include angle brackets; native callback IDs may omit them.
    ids = {event.message_id}
    if provider == "mailgun":
        ids.add("<" + event.message_id.strip("<>") + ">")
        ids.add(event.message_id.strip("<>"))
    scoped = rbac.scope_notification_policy(EmailLog.objects.all(), makerspace_id=space.pk)
    log_ids = list(scoped.filter(provider_name=provider, provider_message_id__in=ids).values_list("pk", flat=True)[:2])
    if len(log_ids) != 1:
        return False  # Includes callback arriving before the accepted log commits.
    event_key = hashlib.sha256(f"{space.pk}:{provider}:{event.event_id}".encode()).hexdigest()
    with tenant_write(space.pk), transaction.atomic():
        from apps.encryption.write_fence import assert_mapped_write_allowed
        assert_mapped_write_allowed(space.pk)
        log = rbac.scope_notification_policy(EmailLog.objects.select_for_update(), makerspace_id=space.pk).get(pk=log_ids[0])
        _, created = EmailProviderWebhookReceipt.objects.get_or_create(
            event_key=event_key, defaults={"makerspace": space, "log": log})
        if not created:
            return True
        ranks = {"": 0, "delivered": 1, "bounce": 2, "complaint": 3}
        if ranks[event.status] > ranks.get(log.provider_delivery_status, 0):
            log.provider_delivery_status = event.status
            log.save(update_fields=["provider_delivery_status", "updated_at"])
        if event.status in {"bounce", "complaint"} and log.provider_recipient_hash:
            rows = rbac.scope_notification_policy(EmailSuppression.objects.all(), makerspace_id=space.pk)
            suppression, _ = rows.get_or_create(makerspace=space, address_hash=log.provider_recipient_hash,
                                                defaults={"reason": event.status})
            suppression = rows.select_for_update().get(pk=suppression.pk)
            if event.status == "complaint" and suppression.reason != "complaint":
                suppression.reason = "complaint"
                suppression.save(update_fields=["reason"])
        audit.record(None, "email.provider_observed", makerspace=space, target=log,
                     meta={"provider": provider, "status": event.status})
    return True
