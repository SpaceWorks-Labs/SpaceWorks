"""Reserve event campaign intents inside the durable batch transaction.

Without a saved choice, email stays with the campaign worker. Its cursor covers every
audience account, including those without verified email, and commits with their envelopes.
The personal outbox recovers broker loss after commit without duplicating email.
"""
from celery import shared_task
from django.db import transaction
from apps.integrations.broadcasts_preferences import has_personal_choice
from apps.integrations.notification_links import local_link

SKIPPED_CHANNELS = ("email",)
EMAIL_RESERVATION = "campaign_email_pipeline"


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
        # Saved selections (including fallback) belong wholly to the resolver.
        # Only the default legacy route reserves email, preventing double sends.
        skipped = () if has_personal_choice(campaign.makerspace, account, "events") else SKIPPED_CHANNELS
        for channel in skipped:
            NotificationDelivery.objects.get_or_create(envelope=envelope, channel=channel, defaults={
                "makerspace": campaign.makerspace, "target_key": channel, "provider": "builtin",
                "state": "skipped", "last_error": EMAIL_RESERVATION})


def legacy_email_eligible(campaign, account):
    """Keep the reserved route stable while rechecking saved choices on retries."""
    from apps.integrations.models_contract import NotificationEnvelope
    from apps.integrations.notification_resolution import resolve
    envelope = NotificationEnvelope.objects.filter(
        makerspace=campaign.makerspace, recipient=account,
        dedup_key=f"ev:broadcast:{campaign.pk}:{account.pk}").first()
    reserved = envelope and envelope.deliveries.filter(
        channel="email", state="skipped", last_error=EMAIL_RESERVATION).exists()
    # An envelope without a reservation owns email even if its choice is later removed.
    if envelope and not reserved:
        return False
    if not has_personal_choice(campaign.makerspace, account, "events"):
        return True
    if not reserved:
        return False
    # A choice saved after legacy dispatch must also govern that pending email.
    # A failed selected channel permits fallback only when both policies allow it.
    other = envelope.deliveries.exclude(channel="email")
    fallback = (other.exists() and not other.filter(state__in={"accepted", "sent", "delivered", "read"}).exists()
                and not other.filter(state="retrying").exists())
    return any(target.channel == "email" for target in resolve(envelope, fallback=fallback))


@shared_task
def event_broadcast_channels(campaign_id, cursor=0):
    # Already queued legacy tasks must use the persisted campaign cursor too.
    from apps.integrations.broadcasts_worker import broadcast_batch
    return broadcast_batch("event_broadcast", campaign_id)
