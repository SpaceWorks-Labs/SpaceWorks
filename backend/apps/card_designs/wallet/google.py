"""Google Wallet generic passes: a signed "Save to Google Wallet" link, and live object
updates through the Wallet REST API with the platform service account.
"""
import base64
import json
import time

import httpx
from django.conf import settings

from .credentials import google_account

CLASS_SUFFIX = "spaceworks_card"
API = "https://walletobjects.googleapis.com/walletobjects/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign_jwt(claims):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    account = google_account()
    key = serialization.load_pem_private_key(account["private_key"].encode(), password=None)
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = key.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{body}.{_b64(signature)}"


def ids(wallet_pass):
    issuer = settings.WALLET_GOOGLE_ISSUER_ID
    return f"{issuer}.{CLASS_SUFFIX}", f"{issuer}.{wallet_pass.serial}"


def wallet_object(wallet_pass, content):
    class_id, object_id = ids(wallet_pass)
    body = {"id": object_id, "classId": class_id,
            "state": "ACTIVE" if content["standing"] == "valid" and not wallet_pass.voided_at else "INACTIVE",
            "cardTitle": {"defaultValue": {"language": "en", "value": content["issuer"][:60]}},
            "header": {"defaultValue": {"language": "en", "value": content["name"][:60] or "Card holder"}},
            "subheader": {"defaultValue": {"language": "en", "value": content["number"] or content["label"]}},
            "hexBackgroundColor": "#006E63",
            "textModulesData": [{"id": "label", "header": content["label"], "body": content["label_value"] or "-"},
                                {"id": "valid", "header": "Valid until", "body": content["valid_until"] or "-"}]}
    if content["qr"]:
        body["barcode"] = {"type": "QR_CODE", "value": content["qr"]}
    return body


def save_link(wallet_pass, content):
    account = google_account()
    claims = {"iss": account["client_email"], "aud": "google", "typ": "savetowallet", "iat": int(time.time()),
              "origins": [], "payload": {"genericObjects": [wallet_object(wallet_pass, content)]}}
    return "https://pay.google.com/gp/v/save/" + sign_jwt(claims)


def _access_token():
    account = google_account()
    now = int(time.time())
    assertion = sign_jwt({"iss": account["client_email"], "scope": "https://www.googleapis.com/auth/wallet_object.issuer",
                          "aud": TOKEN_URL, "iat": now, "exp": now + 3000})
    response = httpx.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                           "assertion": assertion}, timeout=15)
    response.raise_for_status()
    return response.json()["access_token"]


def push_update(wallet_pass, content):
    """PATCH the object, creating the shared class on first use; True on success."""
    headers = {"Authorization": f"Bearer {_access_token()}"}
    class_id, object_id = ids(wallet_pass)
    body = wallet_object(wallet_pass, content)
    response = httpx.patch(f"{API}/genericObject/{object_id}", json=body, headers=headers, timeout=15)
    if response.status_code == 404:
        httpx.post(f"{API}/genericClass", json={"id": class_id}, headers=headers, timeout=15)
        response = httpx.post(f"{API}/genericObject", json=body, headers=headers, timeout=15)
    return response.status_code < 300
