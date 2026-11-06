"""One audited configuration writer for canonical channel settings."""
from django.utils.translation import gettext
from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.tenant_migration.gate_runtime import tenant_write
from .models_endpoints import ChannelConfiguration, WhatsAppTemplate
from .notification_cutover import guarded
from .notification_sender import configuration_sender_key, preserve_configuration


@guarded(mutation=True)
def configure(space, actor, channel, data):
    from apps.accounts import rbac
    from rest_framework.exceptions import PermissionDenied
    if not rbac.is_space_manager_identity(actor, space.pk):
        raise PermissionDenied(gettext("Channel settings require a Space Manager."))
    from .notification_enums import NotificationChannel
    from .notification_config_validation import validate_configuration
    from .messaging.locks import advisory_lock
    if channel not in NotificationChannel.values:
        raise ValidationError({"channel": gettext("Unknown channel.")})
    with tenant_write(space.pk), transaction.atomic():
        type(space).objects.select_for_update(no_key=True).get(pk=space.pk)
        advisory_lock("messaging-settings")
        row, _ = ChannelConfiguration.objects.get_or_create(makerspace=space, channel=channel,
            defaults={"provider": "twilio" if channel in {"whatsapp", "sms"} else
                channel if channel in {"telegram", "slack", "mattermost", "discord", "webhook"} else "builtin"})
        expected = {"twilio", "meta"} if channel == "whatsapp" else {"twilio"} if channel == "sms" else {
            channel} if channel in {"telegram", "slack", "mattermost", "discord", "webhook"} else {"builtin"}
        if data.get("provider", row.provider) not in expected:
            raise ValidationError({"provider": gettext("Provider does not match this channel.")})
        if data.get("room_enabled") and channel not in {"telegram", "slack", "mattermost", "discord", "webhook"}:
            raise ValidationError({"room_enabled": gettext("This channel has no staff rooms.")})
        if data.get("personal_enabled") and channel == "webhook":
            raise ValidationError({"personal_enabled": gettext("Webhooks are staff destinations.")})
        if data.get("use_platform_sender") and channel not in {"sms", "whatsapp"}:
            raise ValidationError({"use_platform_sender": gettext("Platform notification senders are addressed channels only.")})
        validate_configuration(row, data)
        old_sender = row.sender_key
        rotate = any(key in data for key in ("credentials", "integration_identity", "provider", "use_platform_sender"))
        if rotate and (row.credentials or row.integration_identity):
            preserve_configuration(row, retired=True)
        for key, value in data.items():
            if key not in {"credentials", "templates"}:
                setattr(row, key, value)
        if "credentials" in data:
            row.set_credentials(data["credentials"])
        if rotate:
            row.generation += 1
            row.credential_version = row.generation
            row.sender_key = ""  # Derive from the replacement, never a browser-supplied key.
            if channel in {"sms", "whatsapp"}:
                row.sender_key = configuration_sender_key(row)
            row.templates.update(approved=False, needs_review=True)
        if row.personal_enabled and channel in {"telegram", "slack", "mattermost", "discord", "whatsapp"} and not row.integration_identity:
            raise ValidationError({"integration_identity": gettext("Install the integration before enabling personal delivery.")})
        row.save()
        if channel in {"sms", "whatsapp"} and old_sender and old_sender != row.sender_key:
            from .models_messaging_settings import MessagingSenderIdentity
            from .messaging.senders import retire_sender
            for identity in MessagingSenderIdentity.objects.filter(sender_key=old_sender, channel=channel,
                    owner="makerspace", makerspace=space):
                retire_sender(identity)
        if channel in {"sms", "whatsapp"} and row.sender_key:
            from .messaging.senders import reserve_sender
            from .notification_sender import effective_credentials
            values = effective_credentials(row)
            if values and row.credentials:
                reserve_sender(sender_key=row.sender_key, channel=channel, owner="makerspace", makerspace=space,
                    webhook_secret=values.get("auth_token", "") if row.provider == "twilio" else values.get("app_secret", ""),
                    verify_token=values.get("webhook_verify_token", ""), force_rotate=rotate)
            preserve_configuration(row)
        if "templates" in data:
            if channel != "whatsapp":
                raise ValidationError({"templates": gettext("Templates apply to WhatsApp only.")})
            row.templates.all().delete()
            for template in data["templates"]:
                WhatsAppTemplate.objects.create(configuration=row, provider_identity=row.integration_identity,
                    needs_review=True, validation_schema={"body": template.get("variables", [])}, **template)
        audit.record(actor, "notification.channel_configured", makerspace=space, target=row,
            meta={"channel": channel, "fields": sorted(data), "generation": row.generation})
        return row
