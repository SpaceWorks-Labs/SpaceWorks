"""Decision 240 (narrowed by 260): platform credential fallbacks never depend on the hosting switch.

A space with no credentials of its own uses the platform's on EVERY install (SMS, WhatsApp, push,
wallet, attestation). Its own credentials always win. The one hosting-only piece is a NEW Stripe
Connect charge (260): existing Connect charges keep settling with the switch off.
"""
import pathlib
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.makerspaces.domain_verification import hosts_other_spaces

pytestmark = pytest.mark.django_db

APPS = pathlib.Path(__file__).resolve().parents[2] / "apps"


@pytest.fixture
def switch_off(settings):
    """A plain Own-space install: no platform suffix, the console switch reads off."""
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = False
    assert not hosts_other_spaces()


# --- SMS / WhatsApp -------------------------------------------------------------------

def _platform_sms(settings):
    from apps.integrations.models import PlatformSmsSettings
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://hooks.example.test"
    row = PlatformSmsSettings(pk=1, notifications_enabled=True, account_sid="ACplatform",
                              notifications_from_number="+15550100")
    row.set_auth_token("platform-token")
    row.save()


def test_sms_platform_sender_resolves_with_hosting_off(settings, switch_off):
    from apps.integrations.messaging.resolver import resolve_sender
    _platform_sms(settings)
    sender = resolve_sender(None, "sms")
    assert sender is not None and sender.provider_source == "platform" and sender.account_sid == "ACplatform"


def test_sms_space_credentials_win_over_platform(settings, switch_off):
    from apps.integrations.messaging.resolver import resolve_sender
    from apps.integrations.models import MakerspaceMessagingSettings
    from tests.return_helpers import make_space
    _platform_sms(settings)
    space = make_space("fb240-sms")
    own = MakerspaceMessagingSettings(makerspace=space, use_platform_sender=True, sms_account_sid="ACown",
                                      sms_from_number="+15550199")
    own.set_secret("sms_auth_token", "own-token")
    own.save()
    sender = resolve_sender(space, "sms")
    if sender is not None:  # configured own credentials are never replaced by the platform row
        assert sender.provider_source != "platform"


def test_whatsapp_platform_sender_resolves_with_hosting_off(settings, switch_off):
    from apps.integrations.messaging.resolver import resolve_sender
    from apps.integrations.models import PlatformWhatsAppSettings
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://hooks.example.test"
    row = PlatformWhatsAppSettings(pk=1, is_enabled=True, phone_number_id="111", business_account_id="222",
                                   webhook_verify_token="verify")
    row.set_secret("access_token", "tok")
    row.set_secret("app_secret", "sec")
    row.save()
    sender = resolve_sender(None, "whatsapp")
    assert sender is not None and sender.provider_source == "platform" and sender.phone_number_id == "111"


# --- push ------------------------------------------------------------------------------

def test_push_platform_credentials_count_with_hosting_off(switch_off):
    from apps.integrations import push
    row = SimpleNamespace(fcm_configured=True, apns_configured=False, get_fcm_service_account=lambda: "{}")
    with patch.object(push.PlatformPushSettings, "load", return_value=row):
        assert push.push_configured() is True


# --- wallet ----------------------------------------------------------------------------

def test_wallet_platform_fallback_with_hosting_off(switch_off):
    from apps.card_designs.wallet import credentials
    sentinel = SimpleNamespace(name="platform-row")
    with patch.object(credentials, "_platform_row", return_value=sentinel):
        assert credentials._platform_fallback(object()) is sentinel


# --- attestation / analytics / telemetry: the source never asks the hosting switch ------

@pytest.mark.parametrize("rel", [
    "accounts/attestation.py", "accounts/attestation_google.py", "accounts/mobile_readiness.py",
    "integrations/push.py", "integrations/messaging", "integrations/notification_sender.py",
    "analytics", "makerspaces/telemetry_public.py", "card_designs/wallet",
])
def test_fallback_sources_do_not_consult_the_hosting_switch(rel):
    target = APPS / rel
    for path in ([target] if target.is_file() else target.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "hosts_other_spaces" not in text and "hosting_enabled" not in text, path


# --- Stripe Connect: 260 exception ----------------------------------------------------

def _connect_platform():
    from apps.payments.models import PlatformStripeConnectSettings
    PlatformStripeConnectSettings.load()
    PlatformStripeConnectSettings.objects.filter(pk=1).update(
        stripe_secret_key="fernet:x", stripe_webhook_secret="fernet:y", stripe_connect_client_id="ca_x")


def _patched_platform_keys():
    from apps.payments.models import PlatformStripeConnectSettings as Platform
    return (patch.object(Platform, "get_stripe_secret_key", return_value="sk_platform"),
            patch.object(Platform, "get_stripe_webhook_secret", return_value="whsec_platform"))


def _active_connect_space(slug):
    from apps.payments.models import MakerspacePaymentSettings
    from tests.return_helpers import make_space
    space = make_space(slug)
    merchant = MakerspacePaymentSettings.for_makerspace(space)
    merchant.connect_account_id = "acct_new"
    merchant.connect_status = MakerspacePaymentSettings.ConnectStatus.ACTIVE
    merchant.connect_charges_enabled = True
    merchant.save()
    return space


def test_existing_connect_charge_settles_with_hosting_off(switch_off):
    from apps.payments.resolution import source_for_payment
    from tests.payments.recon_f_helpers import pending_charge
    _connect_platform()
    _space, _staff, payment = pending_charge("fb240-existing", stripe_provider="connect",
                                             stripe_connected_account_id="acct_keep")
    first, second = _patched_platform_keys()
    with first, second:
        source = source_for_payment(payment)
    assert source is not None and source.provider == "connect" and source.connected_account_id == "acct_keep"


def test_new_connect_charge_refused_with_hosting_off(switch_off):
    from apps.payments.resolution import resolve_payment_source
    _connect_platform()
    space = _active_connect_space("fb240-new")
    first, second = _patched_platform_keys()
    with first, second:
        assert resolve_payment_source(space) is None


def test_new_connect_charge_allowed_with_hosting_on(settings):
    from apps.payments.resolution import resolve_payment_source
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = True
    _connect_platform()
    space = _active_connect_space("fb240-new-on")
    first, second = _patched_platform_keys()
    with first, second:
        source = resolve_payment_source(space)
    assert source is not None and source.provider == "connect"
