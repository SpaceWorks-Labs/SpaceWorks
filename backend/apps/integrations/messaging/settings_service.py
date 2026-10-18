"""Credential writes and sender reservations commit together; audits name fields only."""
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
    if MakerspaceMessagingSettings.objects.filter(sms_account_sid=row.account_sid).exclude(sms_account_sid="").exists():
        raise ValidationError({"account_sid": "This account is reserved by a tenant sender."})
    if MakerspaceMessagingSettings.objects.filter(sms_from_number=row.from_number).exclude(sms_from_number="").exists():
        raise ValidationError({"from_number": "This number is reserved by a tenant sender."})


def _sync(*, channel, owner, makerspace, key, secret, verify="", force_rotate=False):
    identities = MessagingSenderIdentity.objects.filter(channel=channel, owner=owner, makerspace=makerspace, active=True)
    for identity in identities.exclude(sender_key=key or ""):
        retire_sender(identity)
    if key:
        return reserve_sender(sender_key=key, channel=channel, owner=owner, makerspace=makerspace,
                              webhook_secret=secret, verify_token=verify, force_rotate=force_rotate)


@transaction.atomic
def save_settings(actor, makerspace, values):
    with tenant_write(makerspace.pk):
        space = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
        if not is_servable(space) or not rbac.can(actor, rbac.Action.MANAGE_MAKERSPACE, space.pk):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        advisory_lock("messaging-settings")
        row, _ = MakerspaceMessagingSettings.objects.get_or_create(makerspace=space)
        if not row.whatsapp_webhook_verify_token:
            from apps.integrations.models_messaging_settings import verify_token
            row.whatsapp_webhook_verify_token = verify_token()
        old_business = row.whatsapp_business_account_id
        for key, value in values.items():
            if key in SECRET_FIELDS:
                row.set_secret(key, value)
            elif key in PUBLIC_FIELDS:
                setattr(row, key, value)
        validate_otp_reservation(row.sms_account_sid, row.sms_from_number)
        row.sms_sender_key = sender_key("sms", account_sid=row.sms_account_sid, from_number=row.sms_from_number)
        row.whatsapp_sender_key = sender_key("whatsapp", business_account_id=row.whatsapp_business_account_id,
                                             phone_number_id=row.whatsapp_phone_number_id)
        platform = PlatformWhatsAppSettings.objects.filter(pk=1).first()
        if platform and row.whatsapp_sender_key and row.whatsapp_sender_key == sender_key(
            "whatsapp", business_account_id=platform.business_account_id, phone_number_id=platform.phone_number_id,
        ):
            raise SenderInUse()
        if any(key.startswith("sms_") for key in values):
            _sync(channel="sms", owner="makerspace", makerspace=space, key=row.sms_sender_key,
                  secret=read_secret(row, "sms_auth_token"), force_rotate="sms_auth_token" in values)
        if any(key.startswith("whatsapp_") for key in values):
            _sync(channel="whatsapp", owner="makerspace", makerspace=space, key=row.whatsapp_sender_key,
                  secret=read_secret(row, "whatsapp_app_secret"), verify=row.whatsapp_webhook_verify_token,
                  force_rotate=bool(set(values) & {"whatsapp_access_token", "whatsapp_app_secret"}))
        if old_business != row.whatsapp_business_account_id:
            WhatsAppTemplateBinding.objects.filter(makerspace=space).update(needs_review=True, is_active=False)
        row.save()
        record(actor, "messaging.settings_updated", makerspace=space, target=row, meta={"fields": sorted(values)})
        return row


@transaction.atomic
def sync_platform_sms(row):
    advisory_lock("messaging-settings")
    validate_platform_sms(row)
    previous = PlatformSmsSettings.objects.filter(pk=1).first()
    rotated = bool(previous and previous.auth_token != row.auth_token)
    _sync(channel="sms", owner="platform_otp", makerspace=None,
          key=sender_key("sms", account_sid=row.account_sid, from_number=row.from_number), secret=row.get_auth_token(), force_rotate=rotated)
    _sync(channel="sms", owner="platform", makerspace=None,
          key=sender_key("sms", account_sid=row.account_sid, from_number=row.notifications_from_number), secret=row.get_auth_token(), force_rotate=rotated)
    row.pk = 1
    row.save()


@transaction.atomic
def sync_platform_whatsapp(row):
    advisory_lock("messaging-settings")
    previous = PlatformWhatsAppSettings.objects.filter(pk=1).first()
    if previous and previous.business_account_id != row.business_account_id:
        WhatsAppTemplateBinding.objects.filter(makerspace__isnull=True).update(needs_review=True, is_active=False)
    _sync(channel="whatsapp", owner="platform", makerspace=None,
          key=sender_key("whatsapp", business_account_id=row.business_account_id, phone_number_id=row.phone_number_id),
          secret=row.get_secret("app_secret"), verify=row.webhook_verify_token,
          force_rotate=bool(previous and (previous.access_token != row.access_token or previous.app_secret != row.app_secret)))
    row.pk = 1
    row.save()


def settings_payload(space):
    row = MakerspaceMessagingSettings.objects.filter(makerspace=space).first() or MakerspaceMessagingSettings()
    data = {key: getattr(row, key) for key in PUBLIC_FIELDS}
    data.update({key + "_set": bool(getattr(row, key)) for key in SECRET_FIELDS})
    data["whatsapp_webhook_verify_token"] = row.whatsapp_webhook_verify_token if row.pk else ""
    data["effective_source"] = {channel: getattr(resolve_sender(space, channel), "provider_source", "none") for channel in ("sms", "whatsapp")}
    data["platform_available"] = {channel: resolve_sender(None, channel) is not None for channel in ("sms", "whatsapp")}
    data["webhook_urls"] = {channel: webhook_urls(channel, space.pk) for channel in ("sms", "whatsapp")}
    return data
