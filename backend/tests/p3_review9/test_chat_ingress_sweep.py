"""Non-WhatsApp ingress retains its proof-only / acknowledge-only contract."""
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from rest_framework.test import APIRequestFactory

from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.notification_slack_views import ChatInboundView
from apps.integrations.notification_telegram_callbacks import callback_event

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("channel", ["slack", "discord", "mattermost"])
@pytest.mark.parametrize("switch", ["enabled", "personal_enabled"])
@pytest.mark.parametrize("signed", [True, False])
def test_disabled_chat_hooks_still_authenticate_and_acknowledge_only(twilio_wa, channel, switch, signed):
    wa = twilio_wa
    timestamp = str(int(time.time()))
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    config = ChannelConfiguration.objects.create(makerspace=wa.space, channel=channel, provider=channel,
        enabled=True, personal_enabled=True, integration_identity="chat-installation")
    config.set_credentials({"signing_secret": "slack-secret", "public_key": public_key, "webhook_token": "mm-secret"})
    setattr(config, switch, False)
    config.save()
    # Even text resembling STOP is acknowledge-only on these providers. Neither
    # enabled nor disabled ingress is an account-link / withdrawal protocol.
    raw = json.dumps({"type": 1, "text": "STOP", "token": "mm-secret" if signed else "wrong"}).encode()
    headers = {}
    if channel == "slack":
        signature = "v0=" + hmac.new(b"slack-secret", b"v0:" + timestamp.encode() + b":" + raw, hashlib.sha256).hexdigest()
        headers = {"HTTP_X_SLACK_REQUEST_TIMESTAMP": timestamp, "HTTP_X_SLACK_SIGNATURE": signature if signed else "bad"}
    elif channel == "discord":
        signature = private_key.sign(timestamp.encode() + raw).hex()
        headers = {"HTTP_X_SIGNATURE_TIMESTAMP": timestamp, "HTTP_X_SIGNATURE_ED25519": signature if signed else "00" * 64}
    request = APIRequestFactory().post("/chat/inbound", raw, content_type="application/json", **headers)
    response = ChatInboundView.as_view(channel=channel)(request, makerspace_id=wa.space.pk)
    assert response.status_code == (200 if signed else 403)
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None and wa.endpoint.last_inbound_at is None


@pytest.mark.parametrize("enabled", [True, False])
def test_telegram_only_accepts_private_start_proof_regardless_of_delivery_switch(settings, enabled):
    settings.TELEGRAM_WEBHOOK_SECRET = "telegram-secret"
    config = SimpleNamespace(enabled=enabled, personal_enabled=enabled, integration_identity="telegram-installation")
    message = {"chat": {"type": "private", "id": 123}, "from": {"id": 123}, "text": "STOP"}
    request = SimpleNamespace(headers={"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"}, data={"message": message})
    assert callback_event(config, request) is None
    message["text"] = "/start " + "A" * 43
    event = callback_event(config, request)
    assert event.proof and not event.opt_out
    request.headers["X-Telegram-Bot-Api-Secret-Token"] = "wrong"
    assert callback_event(config, request) is None
