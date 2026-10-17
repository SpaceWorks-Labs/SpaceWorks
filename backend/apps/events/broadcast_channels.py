"""Reserve non-email event campaign intents inside the durable batch transaction.

Email stays with the campaign worker. Its cursor now covers every audience account,
including accounts without verified email, and commits with their personal envelopes.
The personal outbox recovers broker loss after commit without duplicating email.
"""
from celery import shared_task
from django.db import transaction
from apps.integrations.notification_links import local_link

SKIPPED_CHANNELS = ("email",)


def enqueue_channels(campaign_id):
    # Compatibility for callers from before fan-out joined the durable worker.
    from apps.integrations.broadcasts_worker import enqueue
    enqueue("event_broadcast", campaign_id)


def emit_channels(campaign, account):
    from apps.integrations.models_contract import NotificationDelivery
    from apps.integrations.notification_outbox import emit
    from .broadcasts import render_recipient
    values = render_recipient(campaign, account)
    with transaction.atomic():
        envelope = emit(
            makerspace=campaign.makerspace, recipient=account, feature="events", stream="events",
            event="broadcast", audience="member", dedup_key=f"ev:broadcast:{campaign.pk}:{account.pk}",
            source_kind="events.broadcast", source_id=str(campaign.pk), revision="1", subject=campaign,
            context={"campaign_id": campaign.pk, "event_id": campaign.event_id},
            rendered={"subject": values["subject"], "text": values["text_body"], "html": "",
                      "link": local_link(campaign.makerspace, "member")},
        )
        for channel in SKIPPED_CHANNELS:
            NotificationDelivery.objects.get_or_create(envelope=envelope, channel=channel, defaults={
                "makerspace": campaign.makerspace, "target_key": channel, "provider": "builtin",
                "state": "skipped", "last_error": "campaign_email_pipeline"})


@shared_task
def event_broadcast_channels(campaign_id, cursor=0):
    # Already queued legacy tasks must use the persisted campaign cursor too.
    from apps.integrations.broadcasts_worker import broadcast_batch
    return broadcast_batch("event_broadcast", campaign_id)
