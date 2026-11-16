"""A co-hosting organisation's sender name and reply-to (X2, #115a).

Applies to event email only (lifecycle envelopes and event broadcasts) when the hosting
space has `events.organization_sender` on and the event has an active co-hosting
organisation with a sender configured. The From ADDRESS stays the space's: only the
display name becomes "<Organisation> via <Space>" and Reply-To points at the
organisation. The space's provider connection, the email module gate, suppressions and
quotas are untouched, so an organisation can never send through a space that has email
off. Editable by organisation members holding `manage_organization_profile`, and by the
superadmin (#115a); every change is audited as `organization.email_sender_updated`.
"""

import logging
from email.utils import formataddr, parseaddr

logger = logging.getLogger(__name__)
FEATURE = "events.organization_sender"


def _event_id_for(log):
    if log.source_kind == "notification.envelope":
        from .models_contract import NotificationEnvelope
        envelope = NotificationEnvelope.objects.filter(pk=log.source_id, feature="events").only("context").first()
        return (envelope.context or {}).get("event_id") if envelope else None
    if log.source_kind == "event_broadcast":
        from apps.events.models_broadcasts import EventBroadcastDelivery
        return (EventBroadcastDelivery.objects.filter(pk=log.source_id)
                .values_list("campaign__event_id", flat=True).first())
    return None


def sender_for_event(event_id, makerspace):
    from apps.makerspaces.platform import feature_enabled
    from .models_org_sender import OrganizationEmailSender
    if not event_id or makerspace is None or not feature_enabled(makerspace, FEATURE):
        return None
    return (OrganizationEmailSender.objects
            .filter(organization__organized_events__event_id=event_id, organization__is_active=True,
                    organization__organized_events__event__makerspace=makerspace)
            .exclude(sender_name="", reply_to="").order_by("organization_id").first())


def apply(log, msg):
    """Adjust display name and Reply-To in place; any failure leaves the space's sender."""
    try:
        sender = sender_for_event(_event_id_for(log), log.makerspace)
        if sender is None:
            return
        _name, address = parseaddr(msg.from_email)
        if sender.sender_name and address:
            label = f"{sender.sender_name} via {log.makerspace.name}"[:120]
            msg.from_email = formataddr((label, address))
        if sender.reply_to:
            msg.reply_to = [sender.reply_to]
    except Exception:
        logger.warning("organization_sender_apply_failed", extra={"email_log_id": getattr(log, "pk", None)})


def update_sender(organization, actor, *, sender_name, reply_to):
    from django.db import transaction
    from apps.audit.services import record
    from apps.organizations.access import lock_governance_membership
    from apps.organizations.governance import MANAGE_ORGANIZATION_PROFILE
    from apps.organizations.models import Organization
    from .models_org_sender import OrganizationEmailSender
    with transaction.atomic():
        locked = Organization.objects.select_for_update().get(pk=organization.pk)
        lock_governance_membership(actor, locked, MANAGE_ORGANIZATION_PROFILE)
        row, _ = OrganizationEmailSender.objects.select_for_update().get_or_create(organization=locked)
        row.sender_name, row.reply_to, row.updated_by = sender_name, reply_to, actor
        row.save()
        record(actor, "organization.email_sender_updated", target=locked,
               meta={"organization_id": locked.pk, "sender_name_set": bool(sender_name),
                     "reply_to_set": bool(reply_to)})
    return row
