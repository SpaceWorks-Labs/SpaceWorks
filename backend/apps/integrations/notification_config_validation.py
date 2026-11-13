"""Validate a replacement against the same contracts used by provider adapters."""
from django.utils.translation import gettext
from types import SimpleNamespace

from rest_framework.exceptions import ValidationError

from .notification_slack_installation import DiscordInstallationSerializer, MattermostInstallationSerializer


def validate_configuration(row, data):
    enabling_personal = data.get("personal_enabled") and not row.personal_enabled
    if not any(key in data for key in ("credentials", "provider", "integration_identity", "use_platform_sender")) and not enabling_personal:
        return
    provider = data.get("provider", row.provider)
    identity = data.get("integration_identity", row.integration_identity)
    platform_conflict = False
    try:
        values = data["credentials"] if "credentials" in data else row.get_credentials()
        if (row.channel in {"sms", "whatsapp"} and "credentials" in data and not values
                and not data.get("enabled", row.enabled) and not data.get("personal_enabled", row.personal_enabled)
                and not data.get("use_platform_sender", row.use_platform_sender)):
            data["integration_identity"] = ""
            return
        if provider == "slack":
            from .notification_slack import validate_credentials
            if "credentials" in data and not {"bot_token", "team_id"} & set(values) and "integration_identity" not in data:
                identity = ""
            identity = validate_credentials(values, identity, personal=data.get("personal_enabled", row.personal_enabled))
        elif provider in {"mattermost", "discord"}:
            serializer_type = MattermostInstallationSerializer if provider == "mattermost" else DiscordInstallationSerializer
            serializer = serializer_type(data=values)
            serializer.is_valid(raise_exception=True)
            values = dict(serializer.validated_data)
            expected = values["server_url"] if provider == "mattermost" else f"{values['application_id']}:{values['guild_id']}"
            if ("integration_identity" in data or "credentials" not in data) and identity and identity != expected:
                raise ValueError()
            identity = expected
        elif provider == "twilio" and row.channel == "sms":
            import re
            from .messaging.settings_service import validate_otp_reservation
            if not values and data.get("use_platform_sender", row.use_platform_sender):
                from .messaging.resolver import resolve_sender
                sender = resolve_sender(None, "sms")
                if sender is None:
                    raise ValueError()
                identity = sender.sender_key
            else:
                if set(values) != {"account_sid", "auth_token", "from_number"} or not (
                    re.fullmatch(r"AC[0-9a-fA-F]{32}", values.get("account_sid", ""))
                    and re.fullmatch(r"[0-9a-fA-F]{32}", values.get("auth_token", ""))
                    and re.fullmatch(r"\+[1-9][0-9]{6,14}", values.get("from_number", ""))):
                    raise ValueError()
                validate_otp_reservation(values["account_sid"], values["from_number"])
                identity = f"twilio:{values['account_sid']}:{values['from_number']}"
        elif provider == "twilio":
            from .notification_wa_twilio_config import validate_credentials
            validate_credentials(values)
        elif provider == "meta":
            from .notification_wa_meta_http import credentials
            from .notification_sender import effective_credentials
            probe = SimpleNamespace(get_credentials=lambda: values, channel=row.channel, provider=provider,
                use_platform_sender=data.get("use_platform_sender", row.use_platform_sender))
            effective = effective_credentials(probe)
            if not credentials(probe) or set(effective) != {
                "app_id", "app_secret", "business_account_id", "phone_number_id", "access_token", "webhook_verify_token",
            }:
                raise ValueError()
            if ("integration_identity" in data or "credentials" not in data) and identity and identity != effective["phone_number_id"]:
                raise ValueError()
            identity = effective["phone_number_id"]
            if values:
                platform_conflict = _platform_whatsapp_sender(effective)
        elif provider == "telegram":
            if set(values) != {"bot_token"} or not values.get("bot_token"):
                raise ValueError()
        elif provider == "builtin" and values:
            raise ValueError()
    except (ValidationError, ValueError, TypeError, KeyError):
        # Never reflect credentials, URLs or provider error bodies in diagnostics.
        raise ValidationError({"detail": gettext("Invalid or incomplete provider credentials."),
                               "code": "invalid_credentials"}) from None
    if platform_conflict:
        # The platform's physical sender stays reserved even before its registry row
        # is materialized; a tenant cannot claim it with its own credentials.
        from .messaging.senders import SenderInUse
        raise SenderInUse()
    if "credentials" in data:
        data["credentials"] = values
    if identity != row.integration_identity:
        data["integration_identity"] = identity


def _platform_whatsapp_sender(effective):
    """True when own credentials name the platform's physical Meta phone number."""
    from .models_messaging_settings import PlatformWhatsAppSettings
    platform = PlatformWhatsAppSettings.objects.filter(pk=1).first()
    return bool(platform and platform.phone_number_id
                and platform.phone_number_id == effective["phone_number_id"])
