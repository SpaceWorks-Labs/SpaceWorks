"""Canonical SMS/WhatsApp senders shared by the messaging regression tests.

D1 made integration's ChannelConfiguration the only sender authority, so consent
requires a configured canonical sender ("Configure a sender before consenting.").
These helpers build that sender through the audited ``configure()`` writer and the
retained platform settings services; they never weaken the consent rule itself.
"""
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.accounts.models import User
from apps.integrations.messaging.settings_service import sync_platform_sms, sync_platform_whatsapp
from apps.integrations.models import PlatformSmsSettings, PlatformWhatsAppSettings
from apps.integrations.models_contract import NotificationEnvelope
from apps.integrations.models_endpoints import NotificationEndpoint
from apps.integrations.notification_configuration import configure
from tests.fixed_roles.helpers import staff_account

SID = "AC" + "a" * 32
OWN_SID = "AC" + "b" * 32
OTP_FROM, PLATFORM_FROM, OWN_FROM = "+14155550001", "+14155550002", "+14155550003"
PLATFORM_SMS_KEY = f"twilio:{SID}:{PLATFORM_FROM}"
PLATFORM_WA_KEY = "meta:456:123"
OWN_SMS = {"account_sid": OWN_SID, "from_number": OWN_FROM, "auth_token": "c" * 32}


def platform_sms(*, enabled=True, token="twilio-secret"):
    """Platform notification SMS; the OTP number stays separate and reserved."""
    row = PlatformSmsSettings(account_sid=SID, from_number=OTP_FROM,
        notifications_from_number=PLATFORM_FROM, notifications_enabled=enabled)
    row.set_auth_token(token)
    sync_platform_sms(row)
    return PlatformSmsSettings.objects.get(pk=1)


def platform_whatsapp(*, access="meta-access", secret="meta-secret"):
    row = PlatformWhatsAppSettings(is_enabled=True, app_id="789", phone_number_id="123",
                                   business_account_id="456")
    row.set_secret("access_token", access)
    row.set_secret("app_secret", secret)
    sync_platform_whatsapp(row)
    return PlatformWhatsAppSettings.objects.get(pk=1)


def channel_manager(space):
    """The tenant-bound staff Space Manager that owns channel configuration."""
    existing = User.objects.filter(username=f"channels-{space.slug}").first()
    return existing or staff_account(space, f"channels-{space.slug}", "space_manager")


def sms_channel(space, actor=None, *, credentials=None, **values):
    """Platform SMS by explicit tenant opt-in, or own credentials when supplied."""
    data = {"enabled": True, "personal_enabled": True, **values}
    if credentials is None:
        data.setdefault("use_platform_sender", True)
    else:
        data["credentials"] = dict(credentials)
    return configure(space, actor or channel_manager(space), "sms", data)


def whatsapp_channel(space, actor=None, *, credentials=None, **values):
    """Meta WhatsApp via the platform sender, or own Meta credentials when supplied."""
    data = {"provider": "meta", "enabled": True, "personal_enabled": True, **values}
    if credentials is None:
        data.setdefault("use_platform_sender", True)
    else:
        data["credentials"] = dict(credentials)
    return configure(space, actor or channel_manager(space), "whatsapp", data)


def verified_endpoint(user, config, destination=None):
    """A completed signed WhatsApp account-link proof for this installation."""
    destination = destination or user.phone_e164
    now = timezone.now()
    identity = salted_hmac("notification.endpoint.identity.v1",
        f"{config.pk}:{config.generation}:{destination}", algorithm="sha256").hexdigest()
    return NotificationEndpoint.objects.create(makerspace=config.makerspace, user=user, channel="whatsapp",
        provider=config.provider, configuration=config, destination=destination,
        provider_subject=destination, identity_digest=identity,
        integration_identity=config.integration_identity, integration_generation=config.generation,
        verified_at=now, consented_at=now, consent_version="v1")


def envelope(space, user, *, feature="hardware_requests", event="accepted", audience="member", key="m1h",
             source_kind="messaging.test"):
    """A personal intent row; addressed eligibility never trusts its stored snapshot.

    ``migration.history`` marks inert history (no fallback/re-resolution side effects).
    """
    return NotificationEnvelope.objects.create(makerspace=space, recipient=user, feature=feature,
        stream=feature, event=event, audience=audience, source_kind=source_kind,
        source_id="1", dedup_key=f"messaging-test:{key}")
