"""Pure builder checks for wallet passes (no DB): the same properties scripts/dev/verify_wallet_offline.py proves."""
import base64
import io
import json
import shutil
import subprocess
import zipfile

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from apps.card_designs.wallet import apple, google
from apps.card_designs.wallet.credentials import AppleCredentials, GoogleCredentials

from .wallet_material import apple_material, google_material

CONTENT = {"issuer": "Space", "name": "Ada", "number": "M-1", "label": "Plan", "label_value": "Maker",
           "valid_until": "31 Dec 2027", "qr": "SW1:x", "standing": "valid"}


def _apple_creds():
    mat = apple_material()
    return mat, AppleCredentials(mat["apple_pass_type_id"], mat["apple_team_id"], mat["apple_cert_pem"].encode(),
                                 mat["apple_key_pem"].encode(), mat["apple_wwdr_pem"].encode(), "test")


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl not installed")
def test_pkpass_signature_verifies_against_the_chain_and_fails_when_tampered(tmp_path):
    mat, creds = _apple_creds()
    archive = zipfile.ZipFile(io.BytesIO(apple.build_pkpass_bytes(creds, "s1", CONTENT)))
    (tmp_path / "sig").write_bytes(archive.read("signature"))
    (tmp_path / "ca.pem").write_text(mat["apple_wwdr_pem"])

    def verify(manifest):
        (tmp_path / "m").write_bytes(manifest)
        return subprocess.run(["openssl", "smime", "-verify", "-binary", "-inform", "DER", "-in", str(tmp_path / "sig"),
                               "-content", str(tmp_path / "m"), "-CAfile", str(tmp_path / "ca.pem"), "-purpose", "any",
                               "-out", str(tmp_path / "out")], capture_output=True).returncode == 0

    manifest = archive.read("manifest.json")
    assert verify(manifest) and not verify(manifest.replace(b"pass.json", b"pass.jsoN", 1))


def test_apple_pass_json_has_no_pii_fields_and_voids_a_revoked_holder():
    _mat, creds = _apple_creds()
    body = apple.pass_json(creds, "s1", CONTENT).decode().lower()
    assert not any(word in body for word in ("email", "phone", "birth"))
    assert json.loads(apple.pass_json(creds, "s1", {**CONTENT, "standing": "revoked"}))["voided"] is True


def test_google_link_claims_signature_and_voiding():
    mat = google_material()
    account = json.loads(mat["google_service_account"])
    creds = GoogleCredentials(mat["google_issuer_id"], "spaceworks_card", account["client_email"],
                              account["private_key"], "test")
    link = google.link_for(creds, "s_1", CONTENT).removeprefix("https://pay.google.com/gp/v/save/")
    head, body, sig = link.split(".")
    pad = lambda part: base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))  # noqa: E731
    mat["_key"].public_key().verify(pad(sig), f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
    claims = json.loads(pad(body))
    assert (claims["iss"], claims["aud"], claims["typ"], claims["origins"]) == (account["client_email"], "google",
                                                                                "savetowallet", [])
    assert claims["payload"]["genericObjects"][0]["id"] == f"{creds.issuer_id}.s_1"
    voided = google.link_for(creds, "s_1", CONTENT, voided=True).rsplit(".", 2)[1]
    assert json.loads(pad(voided))["payload"]["genericObjects"][0]["state"] == "INACTIVE"
