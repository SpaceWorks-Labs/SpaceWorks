"""One transactional outbox row and quota reservation per logical addressed send."""
import logging

from django.db import transaction

from apps.audit.services import record
from apps.integrations.models import MessagingDelivery
from apps.integrations.recipients_addressed import addressed_recipients
from apps.tenant_migration.gate_runtime import tenant_write
from .eligibility import eligibility, reserve_quota
from .projections import PROJECTION_KEYS, project_context
from .resolver import resolve_sender
from .sources import projection_context, scope_snapshot, source_identity

logger = logging.getLogger(__name__)


def schedule_delivery(pk):
    from apps.integrations.tasks_messaging import deliver_messaging_task
    try:
        deliver_messaging_task.delay(pk)
    except Exception:
        # The durable pending row is retried by the recovery sweep.
        logger.warning("messaging_dispatch_unavailable", extra={"delivery_id": pk})


def enqueue_addressed_messages(makerspace, *, feature, event, event_key, payload, channels=("sms", "whatsapp")):
    result = []
    source_type, source_id = source_identity(feature, payload)
    with tenant_write(makerspace.pk):
        makerspace.refresh_from_db()
        for user_id, audience in addressed_recipients(makerspace, feature, event, payload):
            if (feature, event, audience) not in PROJECTION_KEYS:
                continue
            candidate = MessagingDelivery(makerspace=makerspace, user_id=user_id,
                source_type=source_type, source_id=source_id, feature=feature, event=event, audience=audience)
            context = projection_context(candidate, payload)
            for channel in channels:
                row, created = MessagingDelivery.objects.get_or_create(makerspace=makerspace,
                    event_key=str(event_key), user_id=user_id, channel=channel,
                    defaults={"feature": feature, "event": event, "audience": audience,
                        "context": project_context(feature, event, audience, context),
                        "scope": scope_snapshot(payload.scope), "source_type": source_type, "source_id": source_id})
                result.append(row)
                if not created:
                    continue
                reason = eligibility(row)
                sender = resolve_sender(makerspace, channel)
                if sender:
                    row.sender_key, row.provider, row.provider_source = sender.sender_key, sender.provider, sender.provider_source
                if reason == "ok" and not reserve_quota(row):
                    reason = "quota_exceeded"
                if reason != "ok":
                    row.status = "suppressed" if reason == "suppressed" else "skipped"
                    row.skip_reason = "" if reason == "suppressed" else reason
                row.save(update_fields=["sender_key", "provider", "provider_source", "status", "skip_reason"])
                record(None, "messaging.delivery_enqueued", makerspace=makerspace, target=row,
                       meta={"fields": ["channel", "status", "skip_reason"]})
                if row.status == "pending":
                    transaction.on_commit(lambda pk=row.pk: schedule_delivery(pk), robust=True)
    return result
