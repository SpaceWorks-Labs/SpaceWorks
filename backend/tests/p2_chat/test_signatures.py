import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from rest_framework.test import APIRequestFactory

from apps.integrations.notification_slack import signed_request as slack_signature
from apps.integrations.notification_discord import signed_request as discord_signature
from apps.integrations.notification_slack_views import ChatInboundView


@pytest.mark.parametrize("bad", [False, True])
def test_slack_signature_checks_exact_bytes_and_timestamp(bad):
    timestamp, body = str(int(time.time())), b'{"type":"event_callback"}'
    signature = "v0=" + hmac.new(b"secret", b"v0:" + timestamp.encode() + b":" + body, hashlib.sha256).hexdigest()
    request = SimpleNamespace(body=body + (b" " if bad else b""), headers={
        "X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": signature})
    assert slack_signature(request, "secret") is (not bad)
    request.headers["X-Slack-Request-Timestamp"] = str(int(time.time()) - 301)
    assert not slack_signature(request, "secret")
    assert not slack_signature(request, "")


@pytest.mark.parametrize("bad", [False, True])
def test_discord_ed25519_authenticates_timestamp_and_body(bad):
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    timestamp, body = str(int(time.time())), b'{"type":1}'
    signature = key.sign(timestamp.encode() + body).hex()
    request = SimpleNamespace(body=body + (b" " if bad else b""), headers={
        "X-Signature-Timestamp": timestamp, "X-Signature-Ed25519": signature})
    assert discord_signature(request, public) is (not bad)
    request.headers["X-Signature-Timestamp"] = str(int(time.time()) - 301)
    assert not discord_signature(request, public)


@pytest.mark.django_db
@pytest.mark.parametrize("channel", ["slack", "discord"])
def test_unsigned_invalid_json_is_rejected_before_parsing(chat, channel):
    c = chat(channel)
    request = APIRequestFactory().post("/inbound", b"not-json", content_type="application/json")
    response = ChatInboundView.as_view(channel=channel)(request, makerspace_id=c.space.pk)
    assert response.status_code == 403
    assert response.data["code"] == "invalid_signature"


@pytest.mark.django_db
@pytest.mark.parametrize("valid", [False, True])
def test_mattermost_token_callback_acknowledges_without_state_change(chat, valid):
    c = chat("mattermost")
    request = APIRequestFactory().post("/inbound", {"token": "mm-secret" if valid else "wrong",
        "text": "untrusted text", "user_id": "untrusted"}, format="json")
    response = ChatInboundView.as_view(channel="mattermost")(request, makerspace_id=c.space.pk)
    assert response.status_code == (200 if valid else 403)
    c.endpoint.refresh_from_db()
    assert c.endpoint.last_inbound_at is None
    assert c.endpoint.revoked_at is None


@pytest.mark.django_db
def test_discord_signed_ping(chat):
    c = chat("discord")
    key = Ed25519PrivateKey.generate()
    c.creds["public_key"] = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    c.config.set_credentials(c.creds)
    c.config.save(update_fields=["credentials"])
    body, timestamp = json.dumps({"type": 1}).encode(), str(int(time.time()))
    request = APIRequestFactory().post("/inbound", body, content_type="application/json",
        HTTP_X_SIGNATURE_TIMESTAMP=timestamp,
        HTTP_X_SIGNATURE_ED25519=key.sign(timestamp.encode() + body).hex())
    response = ChatInboundView.as_view(channel="discord")(request, makerspace_id=c.space.pk)
    assert response.status_code == 200 and response.data == {"type": 1}
