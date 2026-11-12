"""Decision 223(k) P3: Apple/Google Wallet passes for guest passes (static, revocable, minimal)."""
import base64
import hashlib
import io
import json
import zipfile

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key, pkcs7
from django.urls import reverse
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.card_designs.models import PlatformWalletCredentials
from apps.card_designs.wallet import credential_service, guest
from apps.makerspaces import guest_pass_issue, guest_pass_lifecycle
from apps.makerspaces.models import GuestPassPolicy
from tests.l3_local.wallet_material import apple_material, google_material, public_fields
from tests.makerspaces.l4_helpers import features_off, features_on, space_with_manager
from tests.makerspaces.test_membership_j1 import user
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db(transaction=True)


def _setup(slug, *, credentials=True):
    makerspace, manager = space_with_manager(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    GuestPassPolicy.objects.get_or_create(makerspace=makerspace, defaults={"sponsor_must_be_present": False})
    features_on(makerspace, "guest_passes", "wallet_passes")
    if credentials:
        row = PlatformWalletCredentials.load()
        credential_service.save(None, row, {**public_fields(apple_material()), **public_fields(google_material())},
                                scope="platform")
    holder = user(f"{slug}-guest")
    return makerspace, manager, holder, guest_pass_issue.issue_staff_pass(manager, makerspace, holder)[0]


def _url(makerspace, guest_pass, platform):
    return reverse("member-guest-pass-wallet", args=[makerspace.pk, guest_pass.pk, platform])


def test_google_link_is_a_signed_jwt_with_minimal_content():
    makerspace, _manager, holder, row = _setup("gw-google")
    response = authenticated_client(holder).post(_url(makerspace, row, "google"))
    assert response.status_code == 201 and response.json()["expires_in"] is None
    token = response.json()["url"].removeprefix("https://pay.google.com/gp/v/save/")
    head, body, signature = token.split(".")
    pad = lambda part: part + "=" * (-len(part) % 4)  # noqa: E731
    claims = json.loads(base64.urlsafe_b64decode(pad(body)))
    stored = PlatformWalletCredentials.load().secret("google_service_account")
    public = load_pem_private_key(json.loads(stored)["private_key"].encode(), None).public_key()
    public.verify(base64.urlsafe_b64decode(pad(signature)), f"{head}.{body}".encode(), padding.PKCS1v15(),
                  hashes.SHA256())
    assert claims["typ"] == "savetowallet" and claims["aud"] == "google"
    obj = claims["payload"]["genericObjects"][0]
    assert obj["barcode"]["value"] == guest.token_for(row) and obj["state"] == "ACTIVE"
    text = json.dumps(claims)
    assert holder.email not in text and "phone" not in text.lower() and "birth" not in text.lower()
    assert AuditLog.objects.filter(action="wallet_pass.guest_issued", meta__platform="google").exists()


def test_apple_pkpass_is_signed_static_and_has_no_personal_data():
    makerspace, _manager, holder, row = _setup("gw-apple")
    response = authenticated_client(holder).post(_url(makerspace, row, "apple"))
    assert response.status_code == 201 and response.json()["expires_in"] == guest.DOWNLOAD_SECONDS
    path = response.json()["url"].split("testserver", 1)[-1]
    download = APIClient().get(path)  # anonymous: the signed one-minute link is the credential
    assert download.status_code == 200 and download["Content-Type"] == "application/vnd.apple.pkpass"
    archive = zipfile.ZipFile(io.BytesIO(download.content))
    manifest = json.loads(archive.read("manifest.json"))
    assert set(manifest) == {"pass.json", "icon.png", "icon@2x.png", "logo.png", "logo@2x.png"}
    for name, digest in manifest.items():
        assert hashlib.sha1(archive.read(name)).hexdigest() == digest
    body = json.loads(archive.read("pass.json"))
    assert "webServiceURL" not in body and "authenticationToken" not in body and body["expirationDate"]
    assert body["barcodes"][0]["message"] == guest.token_for(row) and "voided" not in body
    assert holder.email not in archive.read("pass.json").decode()
    assert pkcs7.load_der_pkcs7_certificates(archive.read("signature"))  # detached PKCS#7 with the signer chain


def test_only_the_holder_may_ask_and_a_tampered_download_link_is_404():
    makerspace, _manager, holder, row = _setup("gw-owner")
    stranger = user("gw-stranger")
    assert authenticated_client(stranger).post(_url(makerspace, row, "google")).status_code == 404
    link = authenticated_client(holder).post(_url(makerspace, row, "apple")).json()["url"]
    path = link.split("testserver", 1)[-1]
    stem = path[:-len(".pkpass")]
    forged = stem[:-1] + ("A" if stem[-1] != "A" else "B") + ".pkpass"
    assert APIClient().get(forged).status_code == 404


def test_a_revoked_pass_cannot_go_into_a_wallet_and_its_qr_stops_scanning():
    makerspace, manager, holder, row = _setup("gw-revoke")
    desk = authenticated_client(manager)
    scan = reverse("admin-guest-pass-scan", args=[makerspace.pk])
    ok = desk.post(scan, {"token": guest.token_for(row)}, format="json").json()
    assert ok["valid"] is True and ok["pass_id"] == row.pk and ok["entitlements"]["presence"] is True
    assert holder.email not in json.dumps(ok)
    guest_pass_lifecycle.revoke_pass(manager, row, "left early")
    gone = desk.post(scan, {"token": guest.token_for(row)}, format="json").json()
    assert gone["valid"] is False and gone["reason"] == "revoked"
    assert authenticated_client(holder).post(_url(makerspace, row, "google")).status_code == 400


def test_forged_tokens_and_other_spaces_resolve_to_unknown():
    makerspace, manager, _holder, row = _setup("gw-forge")
    other, other_manager = space_with_manager("gw-forge-other")
    other.enabled_modules = sorted(set(other.enabled_modules or []) | {"membership"})
    other.save(update_fields=["enabled_modules"])
    features_on(other, "guest_passes")
    token = guest.token_for(row)
    forged = token.rsplit(".", 1)[0] + "." + "0" * 32
    desk = authenticated_client(manager)
    scan = reverse("admin-guest-pass-scan", args=[makerspace.pk])
    assert desk.post(scan, {"token": forged}, format="json").json()["reason"] == "unknown"
    assert desk.post(scan, {"token": "nonsense"}, format="json").json()["reason"] == "unknown"
    cross = authenticated_client(other_manager).post(reverse("admin-guest-pass-scan", args=[other.pk]),
                                                     {"token": token}, format="json")
    assert cross.json()["reason"] == "unknown"
    assert authenticated_client(other_manager).post(scan, {"token": token}, format="json").status_code in (403, 404)


def test_off_without_credentials_or_capabilities():
    makerspace, _manager, holder, row = _setup("gw-off", credentials=False)
    assert guest.platforms_for(row) == []
    assert authenticated_client(holder).post(_url(makerspace, row, "google")).status_code == 400
    row_creds = PlatformWalletCredentials.load()
    credential_service.save(None, row_creds, public_fields(google_material()), scope="platform")
    assert guest.platforms_for(row) == ["google"]
    features_off(makerspace, "wallet_passes")
    row.makerspace.refresh_from_db()  # the pass holds its own cached makerspace instance
    assert guest.platforms_for(row) == []
    features_on(makerspace, "wallet_passes")
    features_off(makerspace, "guest_passes")
    row.makerspace.refresh_from_db()
    assert authenticated_client(holder).post(_url(makerspace, row, "google")).status_code == 404


def test_the_holder_pass_lists_the_wallet_buttons():
    makerspace, _manager, holder, row = _setup("gw-list")
    body = authenticated_client(holder).get(reverse("member-guest-passes", args=[makerspace.pk])).json()
    assert body["passes"][0]["id"] == row.pk and body["passes"][0]["wallet_platforms"] == ["apple", "google"]
