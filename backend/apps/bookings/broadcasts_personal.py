"""Booking campaigns through each recipient's chosen personal channels (plan v2 G.5).

A recipient who has saved a channel choice for the bookings category receives the campaign
as one personal envelope; everyone else keeps the batch worker's email path, so nobody is
messaged twice. Staff rooms never receive campaign bodies.
"""

import logging

from django.utils import timezone

from apps.integrations.broadcasts_templates import render
from apps.makerspaces.platform import member_area_url

from .notification_sources import BROADCAST_SOURCE

logger = logging.getLogger(__name__)


def has_personal_choice(makerspace, account):
    from apps.integrations.notification_resolution import policy_rows
    from apps.notifications.models_preferences import NotificationPreference
    return policy_rows(NotificationPreference, makerspace).filter(user=account, category="bookings").exists()


def personal_content(campaign, account):
    from .broadcasts import bookings
    row = bookings(campaign).filter(member_id=account.pk).order_by("starts_at", "pk").first()
    if row is None:
        return None
    with timezone.override(campaign.makerspace.timezone):
        values = render(campaign.subject, campaign.body, {
            "name": account.get_full_name() or account.username, "resource_name": campaign.space.name,
            "booking_start": timezone.localtime(row.starts_at).isoformat(),
            "booking_end": timezone.localtime(row.ends_at).isoformat(),
            "booking_url": member_area_url(campaign.makerspace),
        })
    return {"subject": values["subject"], "text": values["text_body"], "html": values.get("html_body", ""),
            "link": f"/m/{campaign.makerspace.slug}/member/bookings"}


def emit_personal(campaign, account):
    from apps.integrations.notification_outbox import emit
    rendered = personal_content(campaign, account)
    if rendered is None:
        return None
    try:
        return emit(makerspace=campaign.makerspace, recipient=account, feature="bookings", stream="bookings",
                    event="broadcast", audience="requester", dedup_key=f"bookings.broadcast:{campaign.pk}:{account.pk}",
                    source_kind=BROADCAST_SOURCE, source_id=str(campaign.pk), revision="1", subject=campaign,
                    context={"campaign_id": campaign.pk, "space_id": campaign.space_id}, rendered=rendered)
    except Exception:
        logger.warning("booking_broadcast_envelope_failed", extra={"campaign_id": campaign.pk})
        return None
