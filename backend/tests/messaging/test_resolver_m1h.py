"""Sender resolution on the canonical ChannelConfiguration (D1).

Own credentials take precedence; partial, broken or unreadable own credentials make
the channel unavailable rather than falling back; platform sending needs both the
operator switch and the tenant's explicit ``use_platform_sender``.
"""
import pytest
from rest_framework.exceptions import ValidationError

from apps.integrations.messaging.resolver import resolve_sender
from apps.integrations.messaging.settings_service import sync_platform_sms
from apps.integrations.models import PlatformSmsSettings, PlatformWhatsAppSettings
from tests.messaging.canonical_helpers import (
    OTP_FROM, OWN_FROM, OWN_SID, OWN_SMS, PLATFORM_WA_KEY, SID,
    platform_sms, platform_whatsapp, sms_channel, whatsapp_channel,
)

pytestmark = pytest.mark.django_db


def test_own_precedence_broken_own_no_fallback_and_platform_switch(space, manager):
    platform_sms()
    config = sms_channel(space, manager)
    assert resolve_sender(space, "sms").provider_source == "platform"
    config = sms_channel(space, manager, credentials=OWN_SMS)
    sender = resolve_sender(space, "sms")
    assert sender.provider_source == "own" and sender.from_number == OWN_FROM
    # A broken own credential never falls back to the platform sender.
    config.set_credentials({"account_sid": OWN_SID, "from_number": OWN_FROM})
    config.save(update_fields=["credentials"])
    assert resolve_sender(space, "sms") is None
    # Without own credentials, platform sending still requires the tenant's opt-in.
    config.set_credentials({})
    config.use_platform_sender = False
    config.save(update_fields=["credentials", "use_platform_sender"])
    assert resolve_sender(space, "sms") is None
    config.use_platform_sender = True
    config.save(update_fields=["use_platform_sender"])
    assert resolve_sender(space, "sms").provider_source == "platform"


def test_missing_callback_origin_and_disabled_platform(space, settings):
    row = platform_sms()
    sms_channel(space)
    assert resolve_sender(space, "sms").provider_source == "platform"
    settings.MESSAGING_WEBHOOK_BASE_URL = ""
    assert resolve_sender(space, "sms") is None
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://callbacks.example.test"
    row.notifications_enabled = False
    row.save()
    assert resolve_sender(space, "sms") is None


@pytest.mark.parametrize("values", [{"account_sid": SID}, {"from_number": OTP_FROM}])
def test_otp_account_and_number_reserved_even_when_disabled(space, manager, values):
    platform_sms(enabled=False)
    credentials = {**OWN_SMS, **values}
    with pytest.raises(ValidationError):
        sms_channel(space, manager, credentials=credentials)
    # A stored row carrying OTP credentials is refused at resolution time too.
    config = sms_channel(space, manager, credentials=OWN_SMS)
    config.set_credentials(credentials)
    config.save(update_fields=["credentials"])
    assert resolve_sender(space, "sms") is None


def test_notification_number_cannot_equal_otp():
    row = PlatformSmsSettings(account_sid=SID, from_number="+14155550001", notifications_from_number="+14155550001")
    with pytest.raises(ValidationError):
        sync_platform_sms(row)


def test_whatsapp_resolution_and_incomplete_own(space):
    platform_whatsapp()
    config = whatsapp_channel(space)
    assert resolve_sender(space, "whatsapp").sender_key == PLATFORM_WA_KEY
    # Even one own field means OWN: an incomplete own installation is unavailable.
    config.set_credentials({"phone_number_id": "999"})
    config.save(update_fields=["credentials"])
    assert resolve_sender(space, "whatsapp") is None


def test_platform_key_reserved_without_a_preexisting_registry_row(space, manager):
    from apps.integrations.messaging.senders import SenderInUse
    from apps.integrations.models import MessagingSenderIdentity
    # Deliberately bypass synchronization to cover a configured singleton whose
    # sender reservation has not yet been materialized.
    PlatformWhatsAppSettings.objects.create(pk=1, phone_number_id="123", business_account_id="456")
    assert not MessagingSenderIdentity.objects.filter(sender_key=PLATFORM_WA_KEY).exists()
    own = {"app_id": "111", "app_secret": "own-secret", "business_account_id": "456",
           "phone_number_id": "123", "access_token": "own-access", "webhook_verify_token": "own-verify"}
    with pytest.raises(SenderInUse):
        whatsapp_channel(space, manager, credentials=own)
    assert not MessagingSenderIdentity.objects.filter(sender_key=PLATFORM_WA_KEY).exists()


def test_unreadable_own_credentials_never_fall_back(space):
    platform_sms()
    config = sms_channel(space)
    config.credentials = "fernet:invalid"
    config.save(update_fields=["credentials"])
    assert resolve_sender(space, "sms") is None
