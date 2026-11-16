"""Only the signed account-link proof can grant WhatsApp consent or lift STOP."""
from django.utils import timezone
from contextlib import contextmanager
from contextvars import ContextVar

from .models_messaging_consent import MessagingConsent, MessagingRecipientCorrelation
from .messaging.protections import lock_suppression_key, recipient_hash, suppression_rows
from .notification_sender import configuration_sender_key

_proof_received_at = ContextVar("whatsapp_proof_received_at", default=None)


@contextmanager
def proof_receipt(moment):
    token = _proof_received_at.set(moment)
    try:
        yield
    finally:
        _proof_received_at.reset(token)


def proof_observed_at():
    """Trusted journal time; browser verification always uses the current time."""
    return _proof_received_at.get() or timezone.now()


def record_proof_consent(config, endpoint):
    # consume() already holds cutover, tenant, sender, User and configuration locks.
    sender_key = configuration_sender_key(config)
    phone_hash = recipient_hash("phone", endpoint.destination)
    lock_suppression_key("whatsapp", sender_key, phone_hash)
    received_at = proof_observed_at()
    rows = suppression_rows("whatsapp", sender_key, phone_hash).filter(
        created_at__lte=received_at).select_for_update().order_by("pk")
    lifted = list(rows.values_list("pk", flat=True))
    rows.update(lifted_at=timezone.now())
    from .messaging.protections import suppressed, unmapped_alias_suppressions
    newer_alias_stop = unmapped_alias_suppressions(sender_key).filter(created_at__gt=received_at).exists()
    if not suppressed("whatsapp", sender_key, phone_hash) and not newer_alias_stop:
        MessagingRecipientCorrelation.objects.filter(sender_key=sender_key, phone_hash=phone_hash, state="blocked").delete()
    elif newer_alias_stop:
        MessagingRecipientCorrelation.objects.update_or_create(sender_key=sender_key, phone_hash=phone_hash,
            defaults={"state": "blocked", "alias_known": False})
    user = endpoint.user
    consent = MessagingConsent.objects.create(makerspace=config.makerspace, user=user, channel="whatsapp",
        action="opted_in", source="member_settings", phone_e164=user.phone_e164 or "",
        phone_verified_at=user.phone_verified_at, endpoint=endpoint, sender_key=sender_key,
        configuration_generation=config.generation, lifted_suppression_id=lifted)
    from apps.audit.services import record
    record(user, "messaging.consent_recorded", makerspace=config.makerspace, target=consent,
        meta={"fields": ["channel", "action", "source", "lifted_suppression_id"]})
