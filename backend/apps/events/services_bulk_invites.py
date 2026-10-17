"""Email-bound invitations disclose no admission credential to the mail outbox."""

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.audit.services import record
from apps.integrations.dispatch_outbox import dispatch_email
from apps.integrations.delivery_sources import DeliverySource, register
from apps.integrations.delivery_content import render
from apps.makerspaces.guards import require_module
from . import event_authority
from .event_permissions import MANAGE_INVITATIONS
from .invites import create_invite, code_digest
from .models import Event, EventInvite
from .services_broadcasts import locked_event


def _email_navigation_available(event):
    # Match public detail visibility; email-bound admission does not grant page access.
    return event.is_public and event.status == Event.Status.PUBLISHED and event.ends_at >= timezone.now()


@transaction.atomic
def bulk_invites(event, actor, emails, expires_at=None, send_email=True):
    payload = serializers.ListField(child=serializers.EmailField(), min_length=1, max_length=200).run_validation(emails)
    payload = list(dict.fromkeys(email.strip().lower() for email in payload))
    event = locked_event(event)
    event_authority.require(actor, event, MANAGE_INVITATIONS)
    if send_email:
        require_module(event.makerspace, "email")
        if not _email_navigation_available(event):
            raise serializers.ValidationError({
                "send_email": "Email invitations require a public, published event that has not ended. Turn off email delivery to add only the allowlist.",
            })
    for address in payload:
        invite, _code = create_invite(event, actor=actor, email=address, expires_at=expires_at)
        if send_email:
            account = User.objects.filter(account_kind=User.AccountKind.MEMBER,
                                          email__iexact=address).first()
            dispatch_email(makerspace=event.makerspace, to_email=address, subject="Event invitation",
                           text_body="", stream="events", event="invitation", feature="events", audience="requester",
                           recipient_id=account.pk if account else None, source_kind="event_invitation",
                           source_id=invite.pk, source_metadata={"actor_id": actor.pk})
    record(actor, "event.invitations_added", makerspace=event.makerspace, target=event,
           meta={"count": len(payload), "email_requested": send_email})
    return len(payload)


def prepare_invitation(log):
    import hmac
    from rest_framework.exceptions import APIException
    invite = EventInvite.objects.select_related("event__makerspace").filter(
        pk=log.source_id, makerspace_id=log.makerspace_id,
    ).first()
    if (not invite or invite.makerspace_id != invite.event.makerspace_id or invite.revoked_at or invite.uses >= invite.max_uses
            or invite.expires_at and invite.expires_at <= timezone.now()
            or not hmac.compare_digest(invite.email_digest, code_digest(log.to_email, "email"))):
        return False
    actor = User.objects.filter(pk=log.source_metadata.get("actor_id")).first()
    try:
        event_authority.require(actor, invite.event, MANAGE_INVITATIONS)
        from .invites import require_feature
        require_feature(invite.event, "events.invites")
    except APIException:
        return False
    event = invite.event
    if not _email_navigation_available(event):
        return False
    render(log, subject=f"You're invited: {event.title}",
           text_body=(f"You're invited to {event.title}. Sign in and verify your email to register.\n"
                      f"{settings.PUBLIC_APP_BASE_URL.rstrip('/')}/m/{event.makerspace.slug}/events/{event.public_token}"))
    return True


def register_invitations():
    register("event_invitation", DeliverySource(prepare_invitation, digestible=False))
