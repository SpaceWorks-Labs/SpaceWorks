"""Hosted and native collections protect the same merchant credentials."""

import pytest
from django.core.exceptions import ValidationError

from apps.payments.credential_validation import (
    update_payment_settings, update_platform_payment_settings,
    validate_raw_credential_changes, validate_platform_credential_changes,
)
from apps.payments.models import MakerspacePaymentSettings, Payment, PlatformStripeConnectSettings
from apps.payments.provider_settings import PaymentProviderConflict
from tests.payments.recon_f_helpers import pending_charge

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("field", ["stripe_secret_key", "stripe_webhook_secret"])
@pytest.mark.parametrize("replacement", ["", "rotated"])
@pytest.mark.parametrize("locked", [False, True])
def test_raw_native_handle_blocks_rotation_and_clearing(field, replacement, locked):
    space, _, _ = pending_charge("raw-native-rotation",
        online_rail=Payment.OnlineRail.NATIVE_PAYMENT_INTENT,
        stripe_payment_intent_id="pi_raw_native_rotation")
    merchant = MakerspacePaymentSettings.for_makerspace(space)
    merchant.set_stripe_secret_key("sk_before")
    merchant.set_stripe_webhook_secret("whsec_before")
    merchant.save()
    before = merchant.stripe_secret_key, merchant.stripe_webhook_secret
    change = {field: replacement}
    with pytest.raises(ValidationError) as error:
        if locked:
            update_payment_settings(merchant, change)
        else:
            validate_raw_credential_changes(merchant, change)
    assert field in error.value.message_dict
    merchant.refresh_from_db()
    assert (merchant.stripe_secret_key, merchant.stripe_webhook_secret) == before


@pytest.mark.parametrize("field", ["stripe_secret_key", "stripe_webhook_secret"])
@pytest.mark.parametrize("replacement", ["", "rotated"])
@pytest.mark.parametrize("locked", [False, True])
def test_connect_native_handle_blocks_platform_rotation(field, replacement, locked):
    pending_charge("connect-native-rotation", stripe_provider="connect",
        stripe_connected_account_id="acct_native_rotation",
        online_rail=Payment.OnlineRail.NATIVE_PAYMENT_INTENT,
        stripe_payment_intent_id="pi_connect_native_rotation")
    platform = PlatformStripeConnectSettings.load()
    platform.set_stripe_secret_key("sk_platform_before")
    platform.set_stripe_webhook_secret("whsec_platform_before")
    platform.save()
    before = platform.stripe_secret_key, platform.stripe_webhook_secret
    with pytest.raises(ValidationError) as error:
        if locked:
            update_platform_payment_settings(platform, {field: replacement})
        else:
            validate_platform_credential_changes(platform, {field: replacement})
    assert field in error.value.message_dict
    platform.refresh_from_db()
    assert (platform.stripe_secret_key, platform.stripe_webhook_secret) == before


@pytest.mark.parametrize("provider", ["stripe", "razorpay"])
@pytest.mark.parametrize("rail", ["native_payment_intent", "checkout"])
def test_provider_switch_refuses_live_hosted_and_native_handles(provider, rail):
    handles = ({"stripe_payment_intent_id": "pi_switch"} if provider == "stripe"
               and rail == "native_payment_intent" else
               {"stripe_checkout_session_id": "cs_switch"} if provider == "stripe" else
               {"external_order_id": "order_switch"})
    space, _, _ = pending_charge("switch-collection", provider=provider, online_rail=rail, **handles)
    merchant = MakerspacePaymentSettings.for_makerspace(space)
    merchant.provider = provider
    merchant.save()
    replacement = "razorpay" if provider == "stripe" else "stripe"
    with pytest.raises(PaymentProviderConflict):
        update_payment_settings(merchant, {"provider": replacement})
    merchant.refresh_from_db()
    assert merchant.provider == provider


@pytest.mark.parametrize("provider", ["stripe", "razorpay"])
def test_bare_debt_does_not_block_provider_selection(provider):
    space, _, _ = pending_charge("switch-bare-debt", provider=provider)
    merchant = MakerspacePaymentSettings.for_makerspace(space)
    merchant.provider = provider
    merchant.save()
    replacement = "razorpay" if provider == "stripe" else "stripe"
    assert update_payment_settings(merchant, {"provider": replacement}).provider == replacement


def test_unchanged_raw_keys_and_unrelated_settings_do_not_strand_native_payment():
    space, _, payment = pending_charge("native-unchanged",
        online_rail="native_payment_intent", stripe_payment_intent_id="pi_unchanged")
    merchant = MakerspacePaymentSettings.for_makerspace(space)
    merchant.set_stripe_secret_key("sk_same")
    merchant.save()
    updated = update_payment_settings(merchant, {"stripe_secret_key": "sk_same", "default_currency": "inr"})
    assert updated.default_currency == "inr"
    payment.refresh_from_db()
    assert payment.stripe_payment_intent_id == "pi_unchanged" and payment.status == "pending"


def test_raw_rotation_ignores_other_tenant_native_handles():
    pending_charge("native-other-space", stripe_payment_intent_id="pi_other_space")
    space, _, _ = pending_charge("native-local-space")
    merchant = MakerspacePaymentSettings.for_makerspace(space)
    assert update_payment_settings(merchant, {"stripe_secret_key": "sk_local"}).get_stripe_secret_key() == "sk_local"


def test_raw_rotation_ignores_razorpay_handles(monkeypatch):
    space, _, _ = pending_charge("native-other-vendor", provider="razorpay",
        external_order_id="order_other_vendor", stripe_checkout_session_id="cs_other_vendor")
    merchant = MakerspacePaymentSettings.for_makerspace(space)
    def no_stripe_io(*args, **kwargs):
        pytest.fail("A Razorpay handle must never be looked up at Stripe")
    monkeypatch.setattr("apps.payments.stripe_client.checkout_session_is_closed", no_stripe_io)
    assert update_payment_settings(merchant, {"stripe_secret_key": "sk_new"}).get_stripe_secret_key() == "sk_new"
