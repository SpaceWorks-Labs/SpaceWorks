"""WhatsApp sender lock must be held before entering any of these operations."""
from datetime import timedelta

from django.utils import timezone

from apps.integrations.models import MessagingRecipientAlias, MessagingRecipientCorrelation
from apps.audit.services import record
from .protections import unmapped_alias_suppressions


def claim_probe(delivery, phone_hash, *, reclaimed=False):
    now = timezone.now()
    row, created = MessagingRecipientCorrelation.objects.select_for_update().get_or_create(
        channel="whatsapp", sender_key=delivery.sender_key, phone_hash=phone_hash,
        defaults={"probe_delivery": delivery, "probe_started_at": now})
    if created:
        record(None, "messaging.probe_claimed", makerspace=delivery.makerspace, target=row, meta={"fields": ["state", "probe_delivery"]})
    if row.state == "blocked":
        return "blocked"
    if row.state == "confirmed":
        return "confirmed"
    if row.probe_started_at and row.probe_started_at <= now - timedelta(hours=72):
        return "expired"
    if row.probe_delivery_id != delivery.pk:
        return "wait"
    # A crashed probe may already have reached Meta. Never resubmit it blindly.
    if not created and reclaimed:
        return "ambiguous"
    return "probe"


def map_alias(sender_key, alias_hash, phone_hash):
    if alias_hash and phone_hash:
        row, _ = MessagingRecipientAlias.objects.update_or_create(channel="whatsapp", sender_key=sender_key,
            alias_hash=alias_hash, defaults={"phone_hash": phone_hash})
        record(None, "messaging.alias_correlated", target=row, meta={"fields": ["phone_hash"]})


def release_probe(delivery):
    """Release only a definitively unsubmitted probe, under sender/delivery locks."""
    rows = MessagingRecipientCorrelation.objects.filter(channel="whatsapp", sender_key=delivery.sender_key,
        phone_hash=delivery.recipient_phone_hash, state="probing", probe_delivery=delivery)
    if rows.delete()[0]:
        record(None, "messaging.probe_released", makerspace=delivery.makerspace,
               meta={"delivery_id": delivery.pk, "fields": ["probe_delivery"]})


def confirm_probe(delivery, *, alias_hash="", phone_hash=""):
    addressed = delivery.recipient_phone_hash
    if not addressed or (phone_hash and phone_hash != addressed):
        return
    # Only a callback for our request may assert its alias/phone relationship.
    if alias_hash:
        map_alias(delivery.sender_key, alias_hash, addressed)
        delivery.recipient_alias_hash = alias_hash
    row = MessagingRecipientCorrelation.objects.select_for_update().filter(channel="whatsapp",
        sender_key=delivery.sender_key, phone_hash=addressed, probe_delivery=delivery).first()
    if row is None or row.state == "blocked":
        return
    if alias_hash or (phone_hash == addressed and not unmapped_alias_suppressions(delivery.sender_key).exists()):
        row.state = "confirmed"
        row.alias_known = row.alias_known or bool(alias_hash)
        row.confirmed_at = row.confirmed_at or timezone.now()
        row.save(update_fields=["state", "alias_known", "confirmed_at"])
        record(None, "messaging.probe_confirmed", makerspace=delivery.makerspace, target=row,
               meta={"fields": ["state", "alias_known", "confirmed_at"]})


def claim_canonical_probe(delivery):
    """Caller holds sender lock. Legacy unresolved probes remain an exposure barrier."""
    now = timezone.now()
    row, created = MessagingRecipientCorrelation.objects.select_for_update().get_or_create(
        channel="whatsapp", sender_key=delivery.sender_key, phone_hash=delivery.recipient_phone_hash,
        defaults={"probe_notification_delivery": delivery, "probe_started_at": now})
    if row.state in {"blocked", "confirmed"}:
        return row.state
    if row.probe_started_at and row.probe_started_at <= now - timedelta(hours=72):
        return "expired"
    if row.probe_notification_delivery_id != delivery.pk:
        return "wait"
    return "probe" if created else "ambiguous"


def release_canonical_probe(delivery):
    from django.db import transaction
    from .locks import lock_whatsapp_sender
    with transaction.atomic():
        lock_whatsapp_sender(delivery.sender_key)
        MessagingRecipientCorrelation.objects.filter(sender_key=delivery.sender_key,
            phone_hash=delivery.recipient_phone_hash, state="probing",
            probe_notification_delivery=delivery).delete()


def confirm_canonical_probe(delivery, *, alias_hash="", phone_hash=""):
    """Only a provider-correlated delivery can establish a phone/BSUID alias."""
    addressed = delivery.recipient_phone_hash
    if not addressed or (phone_hash and phone_hash != addressed):
        return
    if alias_hash:
        map_alias(delivery.sender_key, alias_hash, addressed)
        delivery.recipient_alias_hash = alias_hash
    row = MessagingRecipientCorrelation.objects.select_for_update().filter(sender_key=delivery.sender_key,
        phone_hash=addressed, probe_notification_delivery=delivery).first()
    if row is None or row.state == "blocked":
        return
    if alias_hash or (phone_hash == addressed and not unmapped_alias_suppressions(delivery.sender_key).exists()):
        row.state, row.confirmed_at = "confirmed", row.confirmed_at or timezone.now()
        row.alias_known = row.alias_known or bool(alias_hash)
        row.save(update_fields=["state", "confirmed_at", "alias_known"])
