"""Returned setup URLs route to authenticated ingress with the saved generation."""
import base64
import hashlib
import hmac
import json
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

import pytest
from django.urls import resolve, reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.integrations.models_cutover import NotificationIngress
from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.models_messaging_consent import MessagingSuppression
from apps.integrations.notification_api_channels import ChannelSettingsView
from apps.integrations.notification_api_serializers import ChannelSerializer
from apps.integrations.notification_sender import preserve_configuration
from apps.integrations.notification_wa_twilio_views import TwilioWhatsAppWebhookView
from apps.integrations.messaging.protections import recipient_hash
from apps.integrations.messaging.senders import reserve_sender
from tests.account_split.p1_helpers import staff
from .reconciliation_helpers import account, delivery, sms_config, space
from .test_reconciliation_signed_webhooks import twilio_configuration, signed_twilio

pytestmark = pytest.mark.django_db


def signed_form(url, params, token="b" * 32):
    parsed = urlsplit(url)
    public_url = parsed._replace(fragment="").geturl()
    material = public_url + "".join(key + params[key] for key in sorted(params))
    signature = base64.b64encode(hmac.new(token.encode(), material.encode(), hashlib.sha1).digest()).decode()
    return APIRequestFactory().post(parsed.path, urlencode(params), content_type="application/x-www-form-urlencoded",
        HTTP_X_TWILIO_SIGNATURE=signature)


def post_url(request):
    route = resolve(request.path)
    return route.func(request, **route.kwargs)


def test_canonical_sms_settings_urls_reach_signed_sms_ingress(settings, receipt_only_cutover):
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://api.example.test"
    tenant = space()
    config = sms_config(tenant)
    reserve_sender(sender_key=config.sender_key, channel="sms", owner="makerspace", makerspace=tenant,
        webhook_secret="b" * 32)
    manager, _ = staff(tenant, "fm-manager", "space_manager")
    request = APIRequestFactory().get("/")
    force_authenticate(request, manager)
    response = ChannelSettingsView.as_view()(request, makerspace_id=tenant.pk, channel="sms")
    assert response.status_code == 200
    urls = response.data["callback_urls"]
    for kind in ("inbound", "status"):
        url = urls[kind + "_url"]
        assert resolve(urlsplit(url).path).url_name == "messaging-twilio-" + kind
        params = {"AccountSid": "AC" + "a" * 32, "MessageSid": "SM" + "1" * 32,
            "From": "+14155550123" if kind == "inbound" else "+14155550100",
            "To": "+14155550100" if kind == "inbound" else "+14155550123"}
        params.update({"Body": "STOP"} if kind == "inbound" else {"MessageStatus": "failed", "ErrorCode": "21610"})
        assert post_url(signed_form(url, params)).status_code == 200
    assert NotificationIngress.objects.count() == 2
    assert MessagingSuppression.objects.get().recipient_hash == recipient_hash("phone", "+14155550123")


def test_saved_twilio_urls_use_current_generation_and_original_public_base(receipt_only_cutover):
    config = twilio_configuration()
    urls = ChannelSerializer(config).data["callback_urls"]
    assert urls["inbound_url"].startswith("https://api.example.test/")
    assert resolve(urlsplit(urls["inbound_url"]).path).kwargs["generation"] == 2
    params = {"AccountSid": "AC" + "a" * 32, "MessageSid": "SM" + "1" * 32,
        "From": "whatsapp:+14155550123", "To": "whatsapp:+14155550100", "Body": "STOP"}
    assert post_url(signed_form(urls["inbound_url"], params)).status_code == 200
    status = urls["status_url_template"].replace("{delivery_id}", "456")
    route = resolve(urlsplit(status).path)
    assert route.url_name == "whatsapp-twilio-status" and route.kwargs["delivery_id"] == 456
    params.update(From="whatsapp:+14155550100", To="whatsapp:+14155550123", MessageStatus="failed", ErrorCode="21610")
    assert post_url(signed_form(status, params)).status_code == 200
    config.generation = 3
    config.save(update_fields=["generation"])
    assert "/3/inbound" in ChannelSerializer(config).data["callback_urls"]["inbound_url"]


def test_meta_url_reaches_signed_batch_ingress_and_tracks_current_phone(settings, receipt_only_cutover):
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://api.example.test"
    config = ChannelConfiguration(makerspace=space(), channel="whatsapp", provider="meta", generation=7,
        integration_identity="345", sender_key="meta:234:345")
    values = {"app_id": "123", "business_account_id": "234", "phone_number_id": "345",
        "access_token": "access-token", "app_secret": "app-secret", "webhook_verify_token": "verify-token"}
    config.set_credentials(values)
    config.save()
    url = ChannelSerializer(config).data["callback_urls"]["webhook_url"]
    assert resolve(urlsplit(url).path).kwargs == {"makerspace_id": config.makerspace_id, "generation": 7, "phone_number_id": "345"}
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "234", "changes": [{"field": "messages",
        "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "345"},
            "messages": [{"id": "wamid.fm-stop", "from": "14155550123", "type": "text", "text": {"body": "STOP"}}]}}]}]}
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"app-secret", raw, hashlib.sha256).hexdigest()
    request = APIRequestFactory().post(urlsplit(url).path, raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature)
    assert post_url(request).status_code == 200
    assert NotificationIngress.objects.get().protection_applied
    values["phone_number_id"] = "678"
    config.set_credentials(values)
    config.generation = 8
    config.save()
    updated = ChannelSerializer(config).data["callback_urls"]["webhook_url"]
    assert "/8/678/webhook" in updated


def test_recreated_meta_channel_tries_retained_secret_for_same_phone_and_generation(settings, receipt_only_cutover):
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://api.example.test"
    tenant = space()
    old = ChannelConfiguration(makerspace=tenant, channel="whatsapp", provider="meta", generation=2,
        integration_identity="345", sender_key="meta:234:345")
    values = {"app_id": "123", "business_account_id": "234", "phone_number_id": "345",
        "access_token": "access-token", "app_secret": "old-secret", "webhook_verify_token": "old-verify"}
    old.set_credentials(values)
    old.save()
    old_id = old.pk
    url = ChannelSerializer(old).data["callback_urls"]["webhook_url"]
    preserve_configuration(old, retired=True)
    old.delete()
    replacement = ChannelConfiguration(makerspace=tenant, channel="whatsapp", provider="meta", generation=2,
        integration_identity="345", sender_key="meta:234:345")
    replacement.set_credentials({**values, "app_secret": "new-secret", "webhook_verify_token": "new-verify"})
    replacement.save()
    route = resolve(urlsplit(url).path)
    challenge = APIRequestFactory().get(urlsplit(url).path,
        {"hub.mode": "subscribe", "hub.verify_token": "old-verify", "hub.challenge": "opaque"})
    assert route.func(challenge, **route.kwargs).content == b"opaque"
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "234", "changes": [{"field": "messages",
        "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "345"},
            "messages": [{"id": "wamid.retained", "from": "14155550123", "type": "text", "text": {"body": "STOP"}}]}}]}]}
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"old-secret", raw, hashlib.sha256).hexdigest()
    request = APIRequestFactory().post(urlsplit(url).path, raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature)
    assert post_url(request).status_code == 200
    receipt = NotificationIngress.objects.get()
    assert receipt.configuration_reference == old_id and receipt.configuration_id is None


@pytest.mark.parametrize("channel,provider", [("whatsapp", "twilio"), ("whatsapp", "meta"), ("sms", "twilio"), ("email", "builtin")])
def test_incomplete_settings_never_expose_secrets_or_guessed_urls(channel, provider):
    config = ChannelConfiguration.objects.create(makerspace=space(), channel=channel, provider=provider)
    assert ChannelSerializer(config).data["callback_urls"] == {}


def test_recreated_channel_keeps_old_callback_identity_and_expiry(receipt_only_cutover):
    old = twilio_configuration()
    old_id = old.pk
    tenant = old.makerspace
    version = preserve_configuration(old, retired=True)
    request = signed_twilio(old)
    old.delete()
    replacement = ChannelConfiguration.objects.create(makerspace=tenant, channel="whatsapp", provider="twilio",
        generation=2, integration_identity="new-installation")
    values = {"account_sid": "AC" + "a" * 32, "auth_token": "c" * 32,
        "whatsapp_sender": "+14155550100", "public_base_url": "https://api.example.test"}
    replacement.set_credentials(values)
    replacement.save()
    response = TwilioWhatsAppWebhookView.as_view()(request, makerspace_id=tenant.pk, generation=2, kind="inbound")
    assert response.status_code == 200
    receipt = NotificationIngress.objects.get()
    assert receipt.configuration_reference == old_id and receipt.configuration_id is None
    assert receipt.integration_identity == "installation" and receipt.protection_applied
    # The configuration row is gone (SET_NULL); reload before ageing the retired verifier.
    version.refresh_from_db()
    assert version.configuration_id is None
    version.retired_at = timezone.now() - timedelta(days=15)
    version.save(update_fields=["retired_at"])
    assert TwilioWhatsAppWebhookView.as_view()(signed_twilio(old), makerspace_id=tenant.pk,
        generation=2, kind="inbound").status_code == 403


@pytest.mark.parametrize("purge", ["account", "channel"])
def test_signed_21610_survives_deleted_delivery_and_endpoint(receipt_only_cutover, purge):
    from apps.integrations.notification_provider_references import remember
    from apps.integrations.notification_wa_twilio_config import callback_url, validate_credentials
    config = twilio_configuration()
    row = delivery(config.makerspace, account(), channel="whatsapp", state="accepted", provider_id="SM" + "1" * 32,
        sender_key="twilio-wa:AC" + "a" * 32 + ":+14155550100", integration_generation=2,
        integration_identity="installation", recipient_phone_hash=recipient_hash("phone", "+14155550123"))
    remember(row)
    url = callback_url(config, validate_credentials(config.get_credentials()), "status", row.pk)
    row.delete()
    if purge == "channel":
        preserve_configuration(config, retired=True)
        config.delete()
    params = {"AccountSid": "AC" + "a" * 32, "MessageSid": "SM" + "1" * 32,
        "From": "whatsapp:+14155550100", "To": "whatsapp:+14155550123", "MessageStatus": "failed", "ErrorCode": "21610"}
    assert post_url(signed_form(url, params)).status_code == 200
    assert NotificationIngress.objects.get().protection_applied
    assert MessagingSuppression.objects.get().recipient_hash == recipient_hash("phone", "+14155550123")
    receipt_only_cutover.route = "canonical"
    receipt_only_cutover.save(update_fields=["route"])
    from apps.integrations.notification_ingress import process
    assert process(NotificationIngress.objects.get().pk)
