"""Booking selection and live policy; batching/retries belong to integrations."""

from django.db.models import Subquery
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.integrations.broadcasts_registry import BroadcastAdapter, register
from apps.integrations.broadcasts_templates import render
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.platform import member_area_url
from . import booking_authority
from .booking_permissions import MANAGE_RESERVATIONS
from .communication_recipients import recipient_account
from .models import Booking
from .models_broadcasts import BookingBroadcast, BookingBroadcastDelivery

PLACEHOLDERS = ("name", "resource_name", "booking_start", "booking_end", "booking_url")


def authorize(campaign, actor):
    # No relation cached by a task or previous attempt is an authority proof.
    campaign.space.refresh_from_db()
    campaign.space.makerspace.refresh_from_db()
    space = campaign.space
    if campaign.makerspace_id != space.makerspace_id:
        raise PermissionDenied()
    campaign.makerspace = space.makerspace
    booking_authority.require(actor, space, MANAGE_RESERVATIONS)
    require_feature(space.makerspace, "bookings.broadcasts")
    for module in ("notifications", "email"):
        require_module(space.makerspace, module)


def bookings(campaign):
    return Booking.objects.filter(space_id=campaign.space_id, space__makerspace_id=campaign.makerspace_id,
        status__in=campaign.statuses, starts_at__gte=campaign.window_start,
        starts_at__lt=campaign.window_end, starts_at__gt=timezone.now(), member__isnull=False)


def recipients(campaign):
    return User.objects.filter(pk__in=Subquery(bookings(campaign).values("member_id")))


def campaign_enabled(campaign):
    override = campaign.space.requester_notifications_enabled
    return campaign.makerspace.booking_requester_notifications_enabled if override is None else override


def eligible(campaign, account):
    """Email path for the batch worker; a recipient with a personal channel choice gets an envelope instead.

    Called per recipient inside the worker's batch transaction, so the envelope is written
    atomically with the batch cursor. That envelope then resolves the recipient's selected
    channels (email included, under the same verified-email/module/unsubscribe gates) and
    `notification_sources.broadcast_eligible` re-checks the campaign and audience live.
    """
    if not campaign_enabled(campaign) or not bookings(campaign).filter(member_id=account.pk).exists():
        return False
    from .broadcasts_personal import emit_personal, has_personal_choice
    if has_personal_choice(campaign.makerspace, account):
        emit_personal(campaign, account)
        return False
    return bool(recipient_account(campaign.makerspace, account.pk, "broadcast"))


def render_recipient(campaign, account):
    account = recipient_account(campaign.makerspace, account.pk, "broadcast")
    if account is None:
        return None
    row = bookings(campaign).filter(member_id=account.pk).order_by("starts_at", "pk").first()
    if row is None:
        return None
    with timezone.override(campaign.makerspace.timezone):
        values = render(campaign.subject, campaign.body, {
            "name": account.get_full_name() or account.username, "resource_name": campaign.space.name,
            "booking_start": timezone.localtime(row.starts_at).isoformat(),
            "booking_end": timezone.localtime(row.ends_at).isoformat(),
            # Authenticated navigation, no booking/feed/check-in credential.
            "booking_url": member_area_url(campaign.makerspace),
        })
        return {**values, "to_email": account.email}


def register_broadcasts():
    register("booking_broadcast", BroadcastAdapter(BookingBroadcast, BookingBroadcastDelivery, authorize,
        recipients, eligible, render_recipient, "bookings", "booking.broadcast"))
