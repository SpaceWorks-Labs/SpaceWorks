import base64
import hashlib
import hmac
import json
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.integrations.models_cutover import NotificationIngress
from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.models_messaging_consent import MessagingSuppression
from apps.integrations.notification_sender import preserve_configuration
from apps.integrations.notification_wa_twilio_views import TwilioWhatsAppWebhookView
from apps.integrations.notification_wa_meta_views import MetaWebhookView
from .reconciliation_helpers import account, space

pytestmark = pytest.mark.django_db


def twilio_configuration():
    tenant = space()
    config = ChannelConfiguration(makerspace=tenant, channel="whatsapp", provider="twilio",
        generation=2, integration_identity="installation", enabled=False, personal_enabled=False)
    config.set_credentials({"account_sid": "AC" + "a" * 32, "auth_token": "b" * 32,
        "whatsapp_sender": "+14155550100", "public_base_url": "https://api.example.test"})
    config.save()
    return config


def signed_twilio(config, token="b" * 32):
    path = reverse("whatsapp-twilio-inbound", kwargs={"makerspace_id": config.makerspace_id, "generation": 2})
    params = {"AccountSid": "AC" + "a" * 32, "MessageSid": "SM" + "1" * 32,
        "From": "whatsapp:+14155550123", "To": "whatsapp:+14155550100", "OptOutType": "STOP", "Body": "unsubscribe"}
    material = "https://api.example.test" + path + "".join(k + params[k] for k in sorted(params))
    signature = base64.b64encode(hmac.new(token.encode(), material.encode(), hashlib.sha1).digest()).decode()
    return APIRequestFactory().post(path, urlencode(params), content_type="application/x-www-form-urlencoded",
        HTTP_X_TWILIO_SIGNATURE=signature)


def test_signed_twilio_stop_is_stored_while_channel_is_disabled(receipt_only_cutover):
    config = twilio_configuration()
    response = TwilioWhatsAppWebhookView.as_view()(signed_twilio(config), makerspace_id=config.makerspace_id,
        generation=2, kind="inbound")
    assert response.status_code == 200
    assert NotificationIngress.objects.get().protection_applied
    assert MessagingSuppression.objects.filter(channel="whatsapp", lifted_at=None).count() == 1


def test_retired_twilio_secret_authenticates_only_its_old_generation(receipt_only_cutover):
    config = twilio_configuration()
    version = preserve_configuration(config, retired=True)
    values = config.get_credentials()
    values["auth_token"] = "c" * 32
    config.set_credentials(values)
    config.generation = 3
    config.save()
    response = TwilioWhatsAppWebhookView.as_view()(signed_twilio(config), makerspace_id=config.makerspace_id,
        generation=2, kind="inbound")
    assert response.status_code == 200
    assert NotificationIngress.objects.get().generation == 2
    version.retired_at = timezone.now() - timedelta(days=15)
    version.save(update_fields=["retired_at"])
    response = TwilioWhatsAppWebhookView.as_view()(signed_twilio(config), makerspace_id=config.makerspace_id,
        generation=2, kind="inbound")
    assert response.status_code == 403


def test_bad_twilio_signature_does_not_create_receipt_or_suppression(receipt_only_cutover):
    config = twilio_configuration()
    response = TwilioWhatsAppWebhookView.as_view()(signed_twilio(config, "wrong"), makerspace_id=config.makerspace_id,
        generation=2, kind="inbound")
    assert response.status_code == 403
    assert not NotificationIngress.objects.exists()
    assert not MessagingSuppression.objects.exists()


@pytest.mark.parametrize("preference", [False, True])
def test_signed_meta_alias_only_stop_is_durable_without_sms_identity(receipt_only_cutover, preference):
    config = ChannelConfiguration(makerspace=space(), channel="whatsapp", provider="meta", generation=2,
        integration_identity="345", sender_key="meta:234:345", enabled=False, personal_enabled=False)
    config.set_credentials({"app_id": "123", "business_account_id": "234", "phone_number_id": "345",
        "access_token": "access-token", "app_secret": "app-secret", "webhook_verify_token": "verify-token"})
    config.save()
    payload = {"object": "whatsapp_business_account", "entry": [{"id": "234", "changes": [{"field": "messages",
        "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "345"},
            "messages": [{"id": "wamid.alias-stop", "from_user_id": "opaque-bsuid", "type": "text", "text": {"body": "STOP"}}]}}]}]}
    if preference:
        change = payload["entry"][0]["changes"][0]
        change["field"] = "user_preferences"
        change["value"].pop("messages")
        change["value"]["user_preferences"] = [{"user_id": "opaque-bsuid", "value": "stop"}]
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
    kwargs = {"makerspace_id": config.makerspace_id, "generation": 2, "phone_number_id": "345"}
    path = reverse("whatsapp-meta-webhook", kwargs=kwargs)
    request = APIRequestFactory().post(path, body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature)
    response = MetaWebhookView.as_view()(request, **kwargs)
    assert response.status_code == 200
    assert NotificationIngress.objects.get().protection_applied is not preference
    assert MessagingSuppression.objects.get().recipient_kind == ("sender" if preference else "alias")


def test_queued_signed_proof_uses_trusted_receipt_time_but_browser_uses_now(monkeypatch):
    from rest_framework.exceptions import ValidationError
    from apps.integrations.models_endpoints import NotificationEndpointChallenge
    from apps.integrations.notification_proofs import consume, digest
    from apps.integrations.notification_providers import EndpointProof
    from apps.integrations.notification_whatsapp_consent import proof_receipt
    monkeypatch.setattr("apps.integrations.recipients_owners.eligible_owner", lambda *args: True)
    monkeypatch.setattr("apps.integrations.dispatch_channels.channel_module_blocks", lambda *args: False)
    monkeypatch.setattr("apps.makerspaces.servability.is_servable", lambda *args, **kwargs: True)
    tenant, user, now = space(), account(), timezone.now()
    config = ChannelConfiguration.objects.create(makerspace=tenant, channel="whatsapp", provider="meta",
        integration_identity="345", sender_key="meta:234:345", enabled=True, personal_enabled=True)
    code = "x" * 43
    challenge = NotificationEndpointChallenge.objects.create(makerspace=tenant, user=user,
        configuration=config, integration_generation=config.generation, integration_identity="345",
        code_digest=digest(code), expires_at=now - timedelta(minutes=10), consented_at=now - timedelta(minutes=20),
        consent_version="v1")
    NotificationEndpointChallenge.objects.filter(pk=challenge.pk).update(created_at=now - timedelta(minutes=20))
    proof = EndpointProof(code, "+14155550123", "345", "+14155550123", private=True)
    with pytest.raises(ValidationError):
        consume(config, proof)
    with proof_receipt(now - timedelta(minutes=15)):
        endpoint = consume(config, proof)
    assert endpoint.user_id == user.pk and endpoint.consented_at == challenge.consented_at
    challenge.refresh_from_db()
    assert challenge.consumed_at and challenge.endpoint_id == endpoint.pk
