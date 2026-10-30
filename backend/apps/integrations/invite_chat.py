"""Invitations through chat, beside email (X37, NM-40: "wherever email fires, chat is an option").

When an invitation email goes to an address that belongs to an existing, active account
with a verified email, the same invitation is also offered on that person's OWN chat
channels (Telegram, Slack, Discord, Mattermost, WhatsApp, in-app) through the personal
envelope pipeline -- which applies their channel choices, endpoint consent, quiet hours
and the outbound-only rule. The email channel is pre-marked skipped because the
invitation email was already sent directly. The link is single-recipient: it is never
posted to a room, and an address with no matching account gets the email only.

Live source check: the invitation is still open (not redeemed, revoked or expired).
U-B wires staff-role invites to this same helper.
"""

import logging
from hashlib import sha256

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)
SOURCE = "integrations.invitation"
EVENT = "invitation"
INVITE_MODELS = {"events": "events.EventStaffGrantInvite", "bookings": "bookings.BookingSpaceStaffGrantInvite",
                 "members": "organizations.OrganizationInvitation"}


def _account(email):
    from apps.accounts.models import User
    if not email:
        return None
    return User.objects.filter(email__iexact=email.strip(), email_verified_at__isnull=False, is_active=True,
                               access_status="active", is_tenant_dump_stub=False).order_by("pk").first()


def dispatch_invite_chat(makerspace, *, feature, invite, email, label, link):
    """Fail-safe: a chat problem never affects the invitation or its email."""
    from .models_contract import NotificationDelivery
    from .notification_outbox import emit
    try:
        user = _account(email)
        if user is None:
            return None
        with transaction.atomic():
            envelope = emit(
                makerspace=makerspace, recipient=user, feature=feature, stream=feature, event=EVENT,
                audience="member", dedup_key=f"invite:{feature}:{invite.pk}:{sha256(link.encode()).hexdigest()[:24]}",
                source_kind=SOURCE, source_id=str(invite.pk), revision=feature,
                context={"invite_feature": feature},
                rendered={"subject": label, "text": f"{label}. Accept it here: {link}", "html": "", "link": link})
            NotificationDelivery.objects.get_or_create(envelope=envelope, channel="email", defaults={
                "makerspace": makerspace, "target_key": "email", "provider": "builtin",
                "state": "skipped", "last_error": "sent_directly"})
        return envelope
    except Exception:
        logger.warning("invitation_chat_dispatch_failed", extra={"feature": feature, "invite_id": invite.pk})
        return None


def invite_eligible(envelope):
    from django.apps import apps
    label = INVITE_MODELS.get(envelope.context.get("invite_feature"))
    if label is None or envelope.audience != "member":
        return False
    row = apps.get_model(label).objects.filter(pk=envelope.source_id).first()
    if row is None or row.redeemed_at is not None or row.revoked_at is not None or row.expires_at <= timezone.now():
        return False
    if label == "organizations.OrganizationInvitation":
        from apps.organizations.models import OrganizationMakerspace
        return row.organization.is_active and OrganizationMakerspace.objects.filter(
            organization_id=row.organization_id, makerspace_id=envelope.makerspace_id).exists()
    return row.makerspace_id == envelope.makerspace_id


def register():
    from .notification_sources import NotificationSource, register_source
    register_source(SOURCE, NotificationSource(invite_eligible))
