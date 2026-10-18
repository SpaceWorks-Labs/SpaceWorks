"""Sender-level STOP protection survives module removal and tenant source freezes."""
from django.db import transaction

from apps.audit.services import record
from apps.integrations.models import (
    MessagingConsent, MessagingDelivery, MessagingRecipientAlias,
    MessagingRecipientCorrelation, MessagingSuppression, MessagingWebhookEvent,
)
from .correlation import map_alias
from .locks import lock_whatsapp_sender
from .protections import lock_suppression_key, recipient_hash

SMS_STOP = frozenset({"STOP", "STOPALL", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "REVOKE", "OPTOUT"})
WHATSAPP_STOP = SMS_STOP | frozenset({"OPT OUT", "OPT-OUT", "BLOCK"})


@transaction.atomic
def suppress_recipient(channel, sender_key, digest, *, kind="phone", reason="inbound_stop", at=None):
    if channel == "whatsapp":
        lock_whatsapp_sender(sender_key)
    lock_suppression_key(channel, sender_key, digest)
    row, created = MessagingSuppression.objects.get_or_create(channel=channel, sender_key=sender_key,
        recipient_hash=digest, lifted_at__isnull=True,
        defaults={"recipient_kind": kind, "reason": reason, "provider_at": at})
    if created:
        record(None, "messaging.recipient_suppressed", target=row,
               meta={"fields": ["channel", "recipient_kind", "reason"]})
    return row


def process_stop(event):
    """Caller holds the WhatsApp sender lock before locking its durable event."""
    data, channel, sender = event.payload, event.channel, event.sender_key
    alias, phone = data.get("alias_hash", ""), data.get("phone_hash", "")
    from .webhook_processing import provider_timestamp
    at = provider_timestamp(data.get("timestamp"))
    if channel == "whatsapp":
        map_alias(sender, alias, phone)
    if not data.get("stop"):
        return
    if alias:
        suppress_recipient(channel, sender, alias, kind="alias", at=at)
        mapping = MessagingRecipientAlias.objects.filter(channel=channel, sender_key=sender, alias_hash=alias).first()
        if mapping:
            phone = mapping.phone_hash
        else:
            # Context is useful only when it names a message we sent on this sender.
            delivery = MessagingDelivery.objects.filter(channel=channel, sender_key=sender,
                provider_message_id=data.get("context_id") or "__missing__").first()
            if delivery is None:
                from apps.integrations.models_contract import NotificationDelivery
                delivery = NotificationDelivery.objects.filter(channel=channel, sender_key=sender,
                    provider_id=data.get("context_id") or "__missing__").first()
            if delivery and delivery.recipient_phone_hash:
                phone = delivery.recipient_phone_hash
                map_alias(sender, alias, phone)
            else:
                count = MessagingRecipientCorrelation.objects.filter(channel=channel,
                    sender_key=sender, alias_known=False).exclude(state="blocked").update(state="blocked")
                if count:
                    record(None, "messaging.correlations_blocked", meta={"fields": ["state"], "count": count})
    if phone:
        suppress_recipient(channel, sender, phone, at=at)


def append_stop_consents(event):
    """Best effort ledger annotation; protection above never depends on a tenant gate."""
    from apps.accounts.models import User
    from apps.backup.not_restored import TenantNotRestored
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    from apps.tenant_migration.gate_runtime import fanout_tenant_write
    if not event.payload.get("stop"):
        return
    phone = event.payload.get("phone_hash")
    if not phone and event.payload.get("alias_hash"):
        phone = MessagingRecipientAlias.objects.filter(channel=event.channel, sender_key=event.sender_key,
            alias_hash=event.payload["alias_hash"]).values_list("phone_hash", flat=True).first()
    if not phone:
        return
    # Hashes cannot be reversed. Check consent owners against their CURRENT phone
    # and effective sender without retaining any plaintext inbound address.
    owners = MessagingConsent.objects.filter(channel=event.channel).values_list("makerspace_id", "user_id").distinct()
    counts = {"skipped": 0}
    for space_id, user_id in owners.iterator():
        try:
            with fanout_tenant_write(space_id, operation="messaging_stop_consents", counts=counts) as permitted:
                if not permitted:
                    continue
                _append_stop_consent(event, space_id, user_id, phone)
        except (SourceMigrationGateClosed, TenantNotRestored, User.DoesNotExist):
            continue


def _append_stop_consent(event, space_id, user_id, phone):
    from apps.accounts.models import User
    from apps.makerspaces.models import Makerspace
    from apps.tenant_migration.gate_runtime import tenant_write
    from .consent import live_consent
    from .protections import suppressed
    from .resolver import resolve_sender

    with tenant_write(space_id):
        if event.channel == "whatsapp":
            lock_whatsapp_sender(event.sender_key)
        user = User.objects.select_for_update().get(pk=user_id)
        if recipient_hash("phone", user.phone_e164) != phone:
            return
        space = Makerspace.objects.get(pk=space_id)
        sender = resolve_sender(space, event.channel)
        # A newer in-app consent may have lifted STOP after protection committed.
        if (not sender or sender.sender_key != event.sender_key or not live_consent(space, user, event.channel)
            or not suppressed(event.channel, event.sender_key, phone)):
            return
        row = MessagingConsent.objects.create(makerspace=space, user=user, channel=event.channel,
            action="opted_out", source="inbound_stop", phone_e164=user.phone_e164,
            phone_verified_at=user.phone_verified_at)
        record(None, "messaging.consent_recorded", makerspace=space, target=row,
               meta={"fields": ["channel", "action", "source"]})


def annotate_stop(pk):
    """Separate commit avoids inversion of SMS suppression and User consent locks."""
    event = MessagingWebhookEvent.objects.get(pk=pk)
    append_stop_consents(event)
