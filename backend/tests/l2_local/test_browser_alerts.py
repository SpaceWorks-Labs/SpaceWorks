"""X38 browser notifications: RFC 8291 payload round trip, VAPID JWT, SSRF allow-list, opt-in."""
import json
import os
import struct

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.test import override_settings

from apps.notifications import browser_alert_crypto as crypto
from apps.notifications.browser_alerts import allowed_endpoint

KEY = crypto.b64u(os.urandom(32))


def _hkdf(length, salt, info, key):
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(key)


def test_payload_decrypts_with_the_browser_keys():
    browser = ec.generate_private_key(ec.SECP256R1())
    browser_public = browser.public_key().public_bytes(*crypto.POINT)
    auth = os.urandom(16)
    body = crypto.encrypt(b'{"title":"Hi"}', crypto.b64u(browser_public), crypto.b64u(auth))
    salt, (record_size, key_length) = body[:16], struct.unpack("!IB", body[16:21])
    sender_public, ciphertext = body[21:21 + key_length], body[21 + key_length:]
    assert record_size == 4096 and key_length == 65
    sender = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), sender_public)
    ikm = _hkdf(32, auth, b"WebPush: info\x00" + browser_public + sender_public,
                browser.exchange(ec.ECDH(), sender))
    plain = AESGCM(_hkdf(16, salt, b"Content-Encoding: aes128gcm\x00", ikm)).decrypt(
        _hkdf(12, salt, b"Content-Encoding: nonce\x00", ikm), ciphertext, None)
    assert plain == b'{"title":"Hi"}\x02'


def test_vapid_jwt_is_signed_for_the_push_service_origin():
    headers = crypto.vapid_headers("https://fcm.googleapis.com/fcm/send/abc", KEY, "mailto:ops@example.test")
    token = headers["Authorization"].split("t=")[1].split(",")[0]
    head, claims, signature = token.split(".")
    assert json.loads(crypto.unb64u(claims))["aud"] == "https://fcm.googleapis.com"
    raw = crypto.unb64u(signature)
    der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
    crypto.private_key(KEY).public_key().verify(der, f"{head}.{claims}".encode(), ec.ECDSA(hashes.SHA256()))
    assert headers["Content-Encoding"] == "aes128gcm"


@pytest.mark.parametrize("endpoint, ok", [
    ("https://fcm.googleapis.com/fcm/send/x", True),
    ("https://updates.push.services.mozilla.com/wpush/v2/x", True),
    ("https://web.push.apple.com/abc", True),
    ("http://fcm.googleapis.com/x", False),
    ("https://169.254.169.254/latest", False),
    ("https://fcm.googleapis.com.evil.example/x", False),
    ("https://user:pw@fcm.googleapis.com/x", False),
])
def test_only_public_push_services_are_accepted(endpoint, ok):
    assert allowed_endpoint(endpoint) is ok


@pytest.mark.django_db
def test_opt_in_is_404_while_off_or_unconfigured_and_stores_secrets_encrypted(monkeypatch):
    from tests.events.collab_helpers import client_for, make_staff
    from tests.events.ticketing_helpers import event_space
    from tests.l2_local.helpers import on
    from apps.notifications.models_browser_alerts import BrowserAlertSubscription
    space = event_space("browser-alerts")
    space.enabled_modules = sorted(set(space.enabled_modules) | {"notifications"})
    space.save(update_fields=["enabled_modules"])
    staff = make_staff(space)
    url = f"/api/v1/notifications/browser-alerts/{space.pk}"
    browser = ec.generate_private_key(ec.SECP256R1()).public_key().public_bytes(*crypto.POINT)
    body = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc",
            "keys": {"p256dh": crypto.b64u(browser), "auth": crypto.b64u(os.urandom(16))}}
    with override_settings(WEB_PUSH_VAPID_PRIVATE_KEY=KEY, WEB_PUSH_VAPID_SUBJECT="mailto:ops@example.test"):
        assert client_for(staff).post(url, body, format="json").status_code == 404
        on(space, "notifications.web_push")
        response = client_for(staff).post(url, body, format="json")
        assert response.status_code == 200 and response.json() == {"subscribed_browsers": 1}
        row = BrowserAlertSubscription.objects.get(user=staff)
        assert "fcm.googleapis.com" not in row.endpoint and row.get_endpoint() == body["endpoint"]
        bad = {**body, "endpoint": "https://169.254.169.254/x"}
        assert client_for(staff).post(url, bad, format="json").status_code == 400
    assert client_for(staff).get(url).status_code == 404  # unconfigured deployment: dormant
