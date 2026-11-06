"""Optional delivery of an organisation invitation by email and chat (decision #145, X37).

The inviter may name the invitee's email. The address is never stored: the invitation
keeps only an HMAC digest (`invitee_email_digest`, the same scheme resource-grant
invites use), and the raw address lives in memory until the after-commit send. The link
goes once to that address by platform email, and -- only when the address belongs to an
existing, active account with a verified email -- also to that person's own chat channels
through `integrations.invite_chat` in the organisation's own makerspace (owner space,
else the first linked servable space). Never to a room. Failures never undo the invitation.
"""

from django.utils.translation import gettext
import logging
from urllib.parse import quote

from apps.audit import services as audit

logger = logging.getLogger(__name__)
NAMESPACE = "organization"


def email_digest(email):
    from apps.makerspaces.resource_grants_services import credential_digest
    return credential_digest(email, namespace=NAMESPACE, purpose="email") if email else ""


def redeem_link(raw_token):
    from django.conf import settings
    base = str(getattr(settings, "PUBLIC_APP_BASE_URL", "") or "").strip().rstrip("/")
    return f"{base}/organization-invitations/redeem/{quote(raw_token, safe='')}"


def chat_space(organization):
    from apps.makerspaces.servability import servable_q
    from apps.organizations.models import OrganizationMakerspace
    links = (OrganizationMakerspace.objects.filter(servable_q("makerspace"), organization=organization)
             .select_related("makerspace").order_by("pk"))
    owner = next((link for link in links if link.relationship == "owner"), None)
    link = owner or links.first()
    return link.makerspace if link else None


def send(invitation, email, raw_token, actor):
    """After commit: one email, plus a personal chat copy for a verified account."""
    from apps.integrations.dispatch import dispatch_email
    from apps.integrations.invite_chat import dispatch_invite_chat
    organization = invitation.organization
    link = redeem_link(raw_token)
    label = f"You are invited to join {organization.name} on Space Works"
    emailed = chatted = False
    try:
        log = dispatch_email(to_email=email, subject=label, text_body=gettext('{label}. Accept it here: {link}').format(label=label, link=link),
                             makerspace=None, connection="platform", stream="governance",
                             event="organization_invitation", audience="member", persist_body=False, sync=True)
        emailed = getattr(log, "status", "") not in {"failed", "skipped"}
    except Exception:
        logger.warning("organization_invitation_email_failed", extra={"invitation_id": invitation.pk})
    space = chat_space(organization)
    if space is not None:
        chatted = dispatch_invite_chat(space, feature="members", invite=invitation, email=email,
                                       label=label, link=link) is not None
    audit.record(actor, "organization.invitation_delivered", target=invitation,
                 meta={"organization_id": organization.pk, "emailed": emailed, "chat_offered": chatted})
    return emailed, chatted
