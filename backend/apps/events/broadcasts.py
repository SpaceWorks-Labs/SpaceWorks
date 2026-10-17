"""Thin event adapter over the common campaign/outbox pipeline."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db.models import Subquery
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import User
from apps.integrations.broadcasts_registry import BroadcastAdapter, register
from apps.integrations.broadcasts_templates import render
from apps.integrations.email_preferences import blocked_reason
from apps.integrations.notification_catalog import is_notification_enabled
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.servability import is_servable
from apps.makerspaces.website_directory import public_url
from apps.notifications.inbox import eligible_owner
from . import event_authority
from .event_permissions import MANAGE_REGISTRATIONS
from .models import EventRegistration
from .models_broadcasts import EventBroadcast, EventBroadcastDelivery

PLACEHOLDERS = ("name", "event_title", "event_date", "event_location", "ticket_url")


def authorize(campaign, actor):
    event = campaign.event
    if campaign.makerspace_id != event.makerspace_id:
        raise PermissionDenied()
    # Refresh the root on execution: cached relation data is never a policy proof.
    event.makerspace.refresh_from_db()
    if not is_servable(event.makerspace):
        raise PermissionDenied()
    event_authority.require(actor, event, MANAGE_REGISTRATIONS)
    require_feature(event.makerspace, "events.broadcasts")
    for module in ("notifications", "email"):
        require_module(event.makerspace, module)


def registrations(campaign):
    rows = EventRegistration.objects.filter(event_id=campaign.event_id, status__in=campaign.statuses)
    if campaign.attendance == "attended":
        rows = rows.filter(status="attended")
    elif campaign.attendance == "not_attended":
        rows = rows.exclude(status="attended")
    return rows


def recipients(campaign):
    return User.objects.filter(pk__in=Subquery(registrations(campaign).values("member_id")),
                               is_active=True, access_status="active", is_tenant_dump_stub=False)


def eligible(campaign, account):
    if not account.email_verified_at or not account.email or not eligible_owner(campaign.makerspace, account.pk):
        return False
    try:
        validate_email(account.email)
    except DjangoValidationError:
        return False
    return (registrations(campaign).filter(member=account).exists()
            and is_notification_enabled(campaign.makerspace, "events", "email")
            and not blocked_reason(campaign.makerspace, account.email, user_id=account.pk,
                                   feature="events", stream="events", event="broadcast"))


def render_recipient(campaign, account):
    event = campaign.event
    # Registration PK is authenticated navigation identity, never checkin_token.
    registration = registrations(campaign).filter(member=account).select_related(
        "registered_via_makerspace",
    ).order_by("pk").first()
    ticket_space = registration.registered_via_makerspace or event.makerspace
    return render(campaign.subject, campaign.body, {
        "name": account.get_full_name() or account.username,
        "event_title": event.title, "event_date": event.starts_at.isoformat(),
        "event_location": event.location,
        "ticket_url": public_url(ticket_space, "member", f"events/{registration.pk}/ticket"),
    })


def register_broadcasts():
    from .broadcast_channels import emit_channels
    register("event_broadcast", BroadcastAdapter(EventBroadcast, EventBroadcastDelivery, authorize,
             recipients, eligible, render_recipient, "events", "event.broadcast",
             reserve_personal=emit_channels))
