"""Credential writes and sender reservations commit together; audits name fields only."""
from apps.integrations.notification_cutover import guarded
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError

from apps.accounts import rbac
from apps.audit.services import record
from apps.integrations.models import (
    MakerspaceMessagingSettings, MessagingSenderIdentity, PlatformSmsSettings,
    PlatformWhatsAppSettings, WhatsAppTemplateBinding,
)
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import is_servable
from apps.tenant_migration.gate_runtime import tenant_write
from .locks import advisory_lock
from .resolver import resolve_sender, sender_key, webhook_urls
from .senders import SenderInUse, reserve_sender, retire_sender

SECRET_FIELDS = ("sms_auth_token", "whatsapp_access_token", "whatsapp_app_secret")
PUBLIC_FIELDS = ("use_platform_sender", "sms_account_sid", "sms_from_number",
                 "whatsapp_phone_number_id", "whatsapp_business_account_id")


class MessagingCredentialsUnavailable(APIException):
    status_code = 503
    default_detail = {"code": "messaging_credentials_unavailable", "detail": "Re-enter or clear the unreadable provider credential."}


def read_secret(row, field):
    try:
        return row.get_secret(field)
    except Exception:
        raise MessagingCredentialsUnavailable() from None


def validate_otp_reservation(sid, number):
    otp = PlatformSmsSettings.objects.filter(pk=1).first()
    if otp and ((sid and sid == otp.account_sid) or (number and number == otp.from_number)):
        raise ValidationError({"code": "otp_sender_reserved", "detail": "OTP credentials and number are reserved for authentication."})
    platform = sender_key("sms", account_sid=otp.account_sid, from_number=otp.notifications_from_number) if otp else None
    if sid and number and sender_key("sms", account_sid=sid, from_number=number) == platform:
        raise SenderInUse()


def validate_platform_sms(row):
    if row.notifications_from_number and row.notifications_from_number == row.from_number:
        raise ValidationError({"notifications_from_number": "Use a number distinct from the OTP sender."})
    from datetime import timedelta
    from django.db.models import Q
    from django.utils import timezone
    identities = MessagingSenderIdentity.objects.filter(channel="sms", owner="makerspace").filter(
        Q(active=True) | Q(retired_at__gte=timezone.now() - timedelta(days=14)))
    for key in identities.values_list("sender_key", flat=True):
        _, sid, number = key.split(":", 2)
        if (sid and sid == row.account_sid) or (number and number == row.from_number):
            raise ValidationError({"account_sid": "This authentication sender is reserved by a tenant configuration."})


def _sync(*, channel, owner, makerspace, key, secret, verify="", force_rotate=False):
    identities = MessagingSenderIdentity.objects.filter(channel=channel, owner=owner, makerspace=makerspace, active=True)
    for identity in identities.exclude(sender_key=key or ""):
        retire_sender(identity)
    if key:
        return reserve_sender(sender_key=key, channel=channel, owner=owner, makerspace=makerspace,
                              webhook_secret=secret, verify_token=verify, force_rotate=force_rotate)


def save_settings(actor, makerspace, values):
    from apps.integrations.notification_legacy_api import deny_legacy_write
    deny_legacy_write()


@guarded(mutation=True)
@transaction.atomic
def sync_platform_sms(row):
    from apps.integrations.notification_platform_rotation import lock_tenants
    locked_tenants = lock_tenants("sms")
    advisory_lock("messaging-settings")
    validate_platform_sms(row)
    previous = PlatformSmsSettings.objects.filter(pk=1).first()
    rotated = bool(previous and previous.auth_token != row.auth_token)
    changed = previous is None or any(getattr(previous, key) != getattr(row, key) for key in (
        "auth_token", "account_sid", "notifications_from_number", "notifications_enabled"))
    if changed:
        from apps.integrations.notification_platform_rotation import prepare
        prepare("sms", row, locked_tenants)
    _sync(channel="sms", owner="platform_otp", makerspace=None,
          key=sender_key("sms", account_sid=row.account_sid, from_number=row.from_number), secret=row.get_auth_token(), force_rotate=rotated)
    _sync(channel="sms", owner="platform", makerspace=None,
          key=sender_key("sms", account_sid=row.account_sid, from_number=row.notifications_from_number), secret=row.get_auth_token(), force_rotate=rotated)
    row.pk = 1
    row.save()
    if changed:
        from apps.integrations.notification_platform_rotation import finish
        finish("sms")


@guarded(mutation=True)
@transaction.atomic
def sync_platform_whatsapp(row):
    from apps.integrations.notification_platform_rotation import lock_tenants
    locked_tenants = lock_tenants("whatsapp")
    advisory_lock("messaging-settings")
    previous = PlatformWhatsAppSettings.objects.filter(pk=1).first()
    changed = previous is None or any(getattr(previous, key) != getattr(row, key) for key in (
        "access_token", "app_secret", "business_account_id", "phone_number_id", "app_id", "is_enabled"))
    if changed:
        from apps.integrations.notification_platform_rotation import prepare
        prepare("whatsapp", row, locked_tenants)
    _sync(channel="whatsapp", owner="platform", makerspace=None,
          key=sender_key("whatsapp", business_account_id=row.business_account_id, phone_number_id=row.phone_number_id),
          secret=row.get_secret("app_secret"), verify=row.webhook_verify_token,
          force_rotate=bool(previous and (previous.access_token != row.access_token or previous.app_secret != row.app_secret)))
    row.pk = 1
    row.save()
    if changed:
        from apps.integrations.notification_platform_rotation import finish
        finish("whatsapp")


def settings_payload(space):
    row = MakerspaceMessagingSettings.objects.filter(makerspace=space).first() or MakerspaceMessagingSettings()
    data = {key: getattr(row, key) for key in PUBLIC_FIELDS}
    data.update({key + "_set": bool(getattr(row, key)) for key in SECRET_FIELDS})
    data["whatsapp_webhook_verify_token"] = row.whatsapp_webhook_verify_token if row.pk else ""
    data["effective_source"] = {channel: getattr(resolve_sender(space, channel), "provider_source", "none") for channel in ("sms", "whatsapp")}
    data["platform_available"] = {channel: resolve_sender(None, channel) is not None for channel in ("sms", "whatsapp")}
    data["webhook_urls"] = {channel: webhook_urls(channel, space.pk) for channel in ("sms", "whatsapp")}
    return data
