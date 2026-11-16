"""Deliver a staff-role invitation to the invitee only (X37); never back to the inviter.

- one email to the invitation address (the space's mail connection, body not persisted);
- the same single-recipient link on the invitee's own chat channels when the address
  belongs to an existing, verified account (``integrations.invite_chat``);
- the space's staff rooms are told only that an invitation was sent: never the link,
  never the address.

The bearer lives in the URL fragment, so it stays out of access logs and Referer headers.
Every step fails safe: a delivery problem never undoes the invitation.
"""

from django.utils.translation import gettext
import logging
from urllib.parse import urlencode

from django.conf import settings

from apps.integrations.fanout_jobs import deferred_fanout
from apps.makerspaces.models import Makerspace

logger = logging.getLogger(__name__)


def accept_link(invitation, raw):
    space = invitation.makerspace
    base = (settings.PUBLIC_APP_BASE_URL or "").rstrip("/")
    if space.frontend_domain and space.frontend_domain_status == Makerspace.DomainStatus.VERIFIED:
        base = f"https://{space.frontend_domain}"
    return f"{base}/staff-invitations/accept#{urlencode({'token': raw, 'space': space.slug})}"


def _role_names(invitation):
    names = dict(invitation.makerspace.roles.values_list("slug", "name"))
    return ", ".join(names.get(slug, slug) for slug in invitation.role_snapshot) or invitation.role.name


def deliver(invitation, raw):
    """After commit. Returns ``{"delivery_status": ...}`` (never the link)."""
    from apps.integrations.dispatch import dispatch_email
    from apps.integrations.invite_chat import dispatch_invite_chat

    space, link, roles = invitation.makerspace, accept_link(invitation, raw), _role_names(invitation)
    label = f"You are invited to be {roles} at {space.name}"
    status = "unavailable"
    try:
        log = dispatch_email(
            to_email=invitation.email, subject=gettext('Staff invitation to {name}').format(name=space.name),
            text_body=gettext('{label}.\nAccept: {link}\nExpires: {value}.\nSign in to your own account (or create one with this email address) to accept; we will email you a code to confirm the address. If you did not expect this invitation, ignore it.').format(label=label, link=link, value=invitation.expires_at.isoformat()),
            makerspace=space, stream="account", event="staff_invitation", audience="staff",
            persist_body=False, sync=True,
        )
        status = log.status
    except Exception:
        # No exception text or traceback: provider failures can carry credentials.
        logger.warning("staff_invitation_delivery_failed", extra={"invitation_id": invitation.pk})
    dispatch_invite_chat(space, feature="members", invite=invitation, email=invitation.email,
                         label=label, link=link, invite_kind="staff_roles")
    _tell_rooms(invitation, roles)
    return {"delivery_status": status}


@deferred_fanout(feature="members", event="invitation")
def _tell_rooms(invitation, roles):
    from apps.integrations.notify import LifecyclePayload, notify_lifecycle

    text = f"A staff invitation ({roles}) was sent for {invitation.makerspace.name}."
    try:
        notify_lifecycle(invitation.makerspace, feature="members", event="invitation", build=lambda: LifecyclePayload(
            text=text, data={"invitation_id": invitation.pk}, staff_channels_enabled=True))
    except Exception:
        logger.warning("staff_invitation_room_notice_failed", extra={"invitation_id": invitation.pk})
