"""Google Wallet generic passes: a signed "Save to Google Wallet" link, and live object
updates through the Wallet REST API with the space's (else the platform's) service account.
"""
import base64
import json
import time

import httpx

from .credentials import google_for

API = "https://walletobjects.googleapis.com/walletobjects/v1"
TOKEN_URL = "https://oauth2.googleapis.com/token"


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign_jwt(creds, claims):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key = serialization.load_pem_private_key(creds.private_key.encode(), password=None)
    head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = key.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    return f"{head}.{body}.{_b64(signature)}"


def wallet_object(creds, serial, content, *, voided=False):
    body = {"id": f"{creds.issuer_id}.{serial}", "classId": creds.class_id,
            "state": ("INACTIVE" if voided or content["standing"] == "revoked"
                      else "EXPIRED" if content["standing"] == "expired" else "ACTIVE"),
            "cardTitle": {"defaultValue": {"language": "en", "value": content["issuer"][:60]}},
            "header": {"defaultValue": {"language": "en", "value": content["name"][:60] or "Card holder"}},
            "subheader": {"defaultValue": {"language": "en", "value": content["number"] or content["label"]}},
            "hexBackgroundColor": "#006E63",
            "textModulesData": [{"id": "label", "header": content["label"], "body": content["label_value"] or "-"},
                                {"id": "valid", "header": "Valid until", "body": content["valid_until"] or "-"}]}
    if content["qr"]:
        body["barcode"] = {"type": "QR_CODE", "value": content["qr"]}
    if content.get("logo_url"):
        body["logo"] = {"sourceUri": {"uri": content["logo_url"]}}
    if content.get("expires_at"):
        body["validTimeInterval"] = {"end": {"date": content["expires_at"]}}
    return body


def link_for(creds, serial, content, *, voided=False):
    """The signed `pay.google.com/gp/v/save/<jwt>` link carrying one generic object."""
    claims = {"iss": creds.client_email, "aud": "google", "typ": "savetowallet", "iat": int(time.time()),
              "origins": [], "payload": {"genericClasses": [{"id": creds.class_id}],
                          "genericObjects": [wallet_object(creds, serial, content, voided=voided)]}}
    return "https://pay.google.com/gp/v/save/" + sign_jwt(creds, claims)


def save_link(wallet_pass, content):
    creds = google_for(wallet_pass.makerspace_id)
    if creds is None:
        raise LookupError("google wallet credentials are not configured")
    return link_for(creds, wallet_pass.serial, content, voided=bool(wallet_pass.voided_at))


def _access_token(creds):
    now = int(time.time())
    assertion = sign_jwt(creds, {"iss": creds.client_email, "scope": "https://www.googleapis.com/auth/wallet_object.issuer",
                                 "aud": TOKEN_URL, "iat": now, "exp": now + 3000})
    response = httpx.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                           "assertion": assertion}, timeout=15)
    response.raise_for_status()
    return response.json()["access_token"]


def push_update(wallet_pass, content):
    """PATCH the object, creating the shared class on first use; True on success."""
    creds = google_for(wallet_pass.makerspace_id)
    if creds is None:
        return False
    headers = {"Authorization": f"Bearer {_access_token(creds)}"}
    body = wallet_object(creds, wallet_pass.serial, content, voided=bool(wallet_pass.voided_at))
    response = httpx.patch(f"{API}/genericObject/{body['id']}", json=body, headers=headers, timeout=15)
    if response.status_code == 404:
        httpx.post(f"{API}/genericClass", json={"id": creds.class_id}, headers=headers, timeout=15)
        response = httpx.post(f"{API}/genericObject", json=body, headers=headers, timeout=15)
    return response.status_code < 300
