"""Canonical sender ownership, explicit platform opt-in and retired verifier snapshots."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models_cutover import NotificationCredentialVersion


def configuration_sender_key(config):
    if config.sender_key:
        return config.sender_key
    values = effective_credentials(config)
    if config.channel == "sms":
        if values.get("account_sid") and values.get("from_number"):
            return f"twilio:{values['account_sid']}:{values['from_number']}"
        if config.use_platform_sender and not values:
            from .messaging.resolver import resolve_sender
            sender = resolve_sender(None, "sms")
            return sender.sender_key if sender else ""
        return ""
    if not values:
        return ""
    if config.provider == "meta":
        return f"meta:{values.get('business_account_id', '')}:{values.get('phone_number_id', '')}"
    if config.provider == "twilio":
        from .notification_wa_twilio_config import validate_credentials
        parsed = validate_credentials(values)
        return f"twilio-wa:{parsed.account_sid}:{parsed.sender or parsed.messaging_service_sid}"
    return config.integration_identity


def effective_credentials(config):
    """Partial own values refuse fallback; platform sending always needs both opt-ins."""
    values = config.get_credentials()
    if values or not getattr(config, "use_platform_sender", False):
        return values
    if config.channel == "whatsapp" and config.provider == "meta":
        from .models_messaging_settings import PlatformWhatsAppSettings
        platform = PlatformWhatsAppSettings.objects.filter(pk=1, is_enabled=True).first()
        if platform:
            return {"app_id": platform.app_id, "phone_number_id": platform.phone_number_id,
                "business_account_id": platform.business_account_id,
                "access_token": platform.get_secret("access_token"), "app_secret": platform.get_secret("app_secret"),
                "webhook_verify_token": platform.webhook_verify_token}
    return {}


def sms_sender(config):
    from .messaging.resolver import ResolvedSender, resolve_sender, sender_key
    if config.channel != "sms" or config.provider != "twilio" or config.activation_hold:
        return None
    try:
        values = config.get_credentials()
        # Even one own field means OWN, including broken/partial configurations.
        if values:
            from .messaging.settings_service import validate_otp_reservation
            sid, number, token = values.get("account_sid", ""), values.get("from_number", ""), values.get("auth_token", "")
            validate_otp_reservation(sid, number)
            key = sender_key("sms", account_sid=sid, from_number=number)
            if not key or not token:
                return None
            return ResolvedSender("sms", key, "twilio", "own", config.makerspace_id,
                account_sid=sid, from_number=number, auth_token=token)
        if config.use_platform_sender:
            return resolve_sender(None, "sms")
    except Exception:
        return None
    return None


@transaction.atomic
def preserve_configuration(config, *, retired=False):
    import json
    from apps.makerspaces.secrets import encrypt_value
    version = NotificationCredentialVersion.objects.filter(configuration_reference=config.pk,
        generation=config.generation).first()
    if version is None:
        try:
            values = effective_credentials(config)
            stored = config.credentials or (encrypt_value(json.dumps(values)) if values else "")
            sender = configuration_sender_key(config)
        except Exception:
            # Keep unreadable original ciphertext, allowing a replacement to repair
            # the channel without silently replacing historical callback authority.
            stored, sender = config.credentials, config.sender_key
        version, _ = NotificationCredentialVersion.objects.get_or_create(configuration_reference=config.pk,
            generation=config.generation, defaults={"configuration": config,
                "makerspace_reference": config.makerspace_id, "provider": config.provider,
                "integration_identity": config.integration_identity, "sender_key": sender, "credentials": stored})
    if retired and version.retired_at is None:
        version.retired_at = timezone.now()
        version.save(update_fields=["retired_at"])
    return version


def canonical_sender(space, channel):
    from .models_endpoints import ChannelConfiguration
    from .messaging.resolver import ResolvedSender
    config = ChannelConfiguration.objects.filter(makerspace=space, channel=channel).first()
    if config is None or config.activation_hold or not config.enabled or not config.personal_enabled:
        return None
    if channel == "sms":
        return sms_sender(config)
    values = effective_credentials(config)
    if config.provider == "meta":
        from .notification_wa_meta_http import credentials
        if not credentials(config):
            return None
        return ResolvedSender("whatsapp", configuration_sender_key(config), "meta",
            "own" if config.credentials else "platform", space.pk if config.credentials else None,
            phone_number_id=values["phone_number_id"], business_account_id=values["business_account_id"],
            access_token=values["access_token"], app_secret=values["app_secret"], verify_token=values["webhook_verify_token"])
    if config.provider == "twilio":
        from .notification_wa_twilio_config import validate_credentials
        parsed = validate_credentials(values)
        return ResolvedSender("whatsapp", configuration_sender_key(config), "twilio", "own", space.pk,
            account_sid=parsed.account_sid, from_number=parsed.sender, auth_token=parsed.auth_token)
    return None


def callback_configurations(makerspace_id, provider, generation):
    from .models_endpoints import ChannelConfiguration
    config = ChannelConfiguration.objects.filter(makerspace_id=makerspace_id,
        channel="whatsapp").first()
    candidates = [config] if config and config.provider == provider and config.generation == generation else []
    from django.db.models import Q
    versions = NotificationCredentialVersion.objects.filter(makerspace_reference=makerspace_id,
        provider=provider, generation=generation, wiped_at=None).filter(
            Q(retired_at=None) | Q(retired_at__gte=timezone.now() - timedelta(days=14)))
    # Retained installations keep their original PK, even after purge/recreation.
    return candidates + [ChannelConfiguration(pk=v.configuration_reference, makerspace_id=makerspace_id,
        channel="whatsapp", provider=provider, generation=generation, credentials=v.credentials,
        sender_key=v.sender_key, integration_identity=v.integration_identity,
        credential_version=v.generation) for v in versions]
