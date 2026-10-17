"""Event campaigns on each recipient's chosen personal channels (v2 §G.5).

The shared campaign worker keeps owning EMAIL exactly as before (verified address, email
module, unsubscribe gates, batching, retries, campaign status). This fan-out adds the other
personal channels: one envelope per audience account, whose email delivery is pre-marked
skipped so a person who also selected email never gets the campaign twice. Inclusion on a
channel is still decided live by the shared layer (enabled for the space, verified and
consented endpoint, category preference), and `notification_sources.broadcast_eligible`
re-checks the campaign status, the original sender's authority and the live audience at
every send. Staff rooms never receive campaign bodies: no room path is involved at all.
"""

import logging

from celery import shared_task
from django.db import transaction
from apps.integrations.notification_links import local_link

logger = logging.getLogger(__name__)
BATCH_SIZE = 200
SKIPPED_CHANNELS = ("email",)  # owned by the campaign worker


def enqueue_channels(campaign_id):
    try:
        event_broadcast_channels.delay(campaign_id)
    except Exception:
        logger.warning("event_broadcast_channels_enqueue_failed", extra={"campaign_id": campaign_id})


def _emit(campaign, account):
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
    from apps.accounts.models import User
    from rest_framework.exceptions import APIException
    from .broadcasts import authorize, registrations
    from .models_broadcasts import EventBroadcast

    campaign = EventBroadcast.objects.select_related("event__makerspace", "makerspace", "created_by").filter(
        pk=campaign_id).first()
    if campaign is None or campaign.status not in {"queued", "sending", "sent", "failed"}:
        return 0
    try:
        authorize(campaign, campaign.created_by)  # original sender, re-read every batch
    except APIException:
        return 0
    accounts = list(User.objects.filter(
        pk__in=registrations(campaign).values("member_id"), pk__gt=cursor, is_active=True,
        access_status="active", is_tenant_dump_stub=False).order_by("pk")[:BATCH_SIZE])
    for account in accounts:
        try:
            _emit(campaign, account)
        except Exception:
            logger.warning("event_broadcast_channel_emit_failed", extra={"campaign_id": campaign.pk})
    if len(accounts) == BATCH_SIZE:
        try:
            event_broadcast_channels.delay(campaign_id, accounts[-1].pk)
        except Exception:
            logger.warning("event_broadcast_channels_enqueue_failed", extra={"campaign_id": campaign_id})
    return len(accounts)
