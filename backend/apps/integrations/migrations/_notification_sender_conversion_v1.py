"""Frozen sender reservations for canonical installations; ambiguity never chooses an owner."""
from django.db.models import Max

from apps.makerspaces.secrets import decrypt_value, encrypt_value


def reserve(registry, alias, config, values):
    Config = registry.get_model("integrations", "ChannelConfiguration")
    Identity = registry.get_model("integrations", "MessagingSenderIdentity")
    Credential = registry.get_model("integrations", "MessagingSenderCredential")
    if not config.sender_key or not config.credentials:
        return
    peers = Config.objects.using(alias).filter(channel=config.channel,
        sender_key=config.sender_key).exclude(pk=config.pk).exclude(credentials="")
    if peers.exists():
        peers.update(activation_hold=True)
        config.activation_hold = True
    identity, _ = Identity.objects.using(alias).get_or_create(sender_key=config.sender_key,
        defaults={"channel": config.channel, "owner": "makerspace", "makerspace_id": config.makerspace_id,
            "tenant_reference": config.makerspace_id})
    if identity.owner != "makerspace" or identity.makerspace_id != config.makerspace_id or not identity.active:
        config.activation_hold = True
        return
    secret = values.get("auth_token", "") if config.provider == "twilio" else values.get("app_secret", "")
    current = Credential.objects.using(alias).filter(identity=identity, retired_at=None).first()
    if current:
        try:
            if decrypt_value(current.webhook_secret) != secret:
                config.activation_hold = True
        except Exception:
            config.activation_hold = True
    elif secret:
        version = (Credential.objects.using(alias).filter(identity=identity).aggregate(n=Max("version"))["n"] or 0) + 1
        Credential.objects.using(alias).create(identity=identity, version=version,
            webhook_secret=encrypt_value(secret), verify_token=values.get("webhook_verify_token", ""))


def remember_reference(registry, alias, delivery):
    if not delivery.provider_id or not delivery.sender_key or delivery.channel not in {"sms", "whatsapp"}:
        return
    Reference = registry.get_model("integrations", "NotificationProviderReference")
    row, _ = Reference.objects.using(alias).get_or_create(provider=delivery.provider,
        sender_key=delivery.sender_key, provider_id=delivery.provider_id,
        defaults={"phone_hash": delivery.recipient_phone_hash, "delivery_reference": delivery.pk,
            "makerspace_reference": delivery.makerspace_id, "generation": delivery.integration_generation,
            "attempt": delivery.attempt_count})
    if (row.delivery_reference != delivery.pk or row.generation != delivery.integration_generation
            or row.attempt != delivery.attempt_count or row.makerspace_reference != delivery.makerspace_id):
        row.ambiguous = True
        row.save(using=alias, update_fields=["ambiguous"])
