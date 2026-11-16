"""Decision 253(c): a wallet pass is voided only when revoked/converted; an expired pass shows as expired."""
import base64
import json
from types import SimpleNamespace

from apps.card_designs.wallet import apple, google
from apps.card_designs.wallet.credentials import AppleCredentials, GoogleCredentials
from tests.l3_local.wallet_material import apple_material, google_material

CONTENT = {"issuer": "Space", "name": "Ada", "number": "M-1", "label": "Plan", "label_value": "Maker",
           "valid_until": "31 Dec 2027", "qr": "SW1:x", "standing": "valid"}


def _apple():
    m = apple_material()
    return AppleCredentials(m["apple_pass_type_id"], m["apple_team_id"], m["apple_cert_pem"].encode(),
                            m["apple_key_pem"].encode(), m["apple_wwdr_pem"].encode(), "test")


def _google():
    m = google_material()
    account = json.loads(m["google_service_account"])
    return GoogleCredentials(m["google_issuer_id"], "spaceworks_card", account["client_email"],
                             account["private_key"], "test")


def _state(link):
    body = link.rsplit(".", 2)[1]
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    return claims["payload"]["genericObjects"][0]["state"]


def test_expired_apple_pass_is_not_voided_and_carries_an_expiration_date():
    body = json.loads(apple.pass_json(_apple(), "s1", {**CONTENT, "standing": "expired"}))
    assert "voided" not in body and body["expirationDate"]


def test_expired_pass_keeps_its_own_expiry_date_when_the_content_has_one():
    body = json.loads(apple.pass_json(_apple(), "s1", {**CONTENT, "standing": "expired",
                                                       "expires_at": "2026-01-01T00:00:00Z"}))
    assert body["expirationDate"] == "2026-01-01T00:00:00Z" and "voided" not in body


def test_revoked_and_converted_apple_passes_are_voided():
    assert json.loads(apple.pass_json(_apple(), "s1", {**CONTENT, "standing": "revoked"}))["voided"] is True
    converted = SimpleNamespace(voided_at="2026-11-01T00:00:00Z")
    assert json.loads(apple.pass_json(_apple(), "s1", CONTENT, wallet_pass=converted))["voided"] is True


def test_google_states_expired_is_expired_not_inactive():
    creds = _google()
    assert _state(google.link_for(creds, "s_1", {**CONTENT, "standing": "expired"})) == "EXPIRED"
    assert _state(google.link_for(creds, "s_1", {**CONTENT, "standing": "revoked"})) == "INACTIVE"
    assert _state(google.link_for(creds, "s_1", CONTENT, voided=True)) == "INACTIVE"
    assert _state(google.link_for(creds, "s_1", CONTENT)) == "ACTIVE"
