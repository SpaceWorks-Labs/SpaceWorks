"""Decision 246 (lane T4): service-level wallet conditions (223 credentials, 240 platform fallback).

Uses throw-away generated certificates and keys (`wallet_material`), like the offline builder tests.
Calls `credential_service.save`, `credentials.apple_for/google_for` and the pass builders directly:
the whole fallback chain space -> platform -> deployment files, off without credentials, an
idempotent re-save, cross-space isolation of one space's own credentials, a revoked holder's pass
voided, and no personal or money fields in a pass.
"""
import base64
import json

import pytest

from apps.audit.models import AuditLog
from apps.card_designs.models import MakerspaceWalletCredentials
from apps.card_designs.wallet import apple, credential_service, google
from apps.card_designs.wallet.credentials import GoogleCredentials, apple_for, configured_platforms, google_for
from tests.l3_local.wallet_material import apple_material, google_material, public_fields
from tests.makerspaces.l4_helpers import space_with_manager

pytestmark = pytest.mark.django_db

CONTENT = {"issuer": "Space", "name": "Ada", "number": "M-1", "label": "Plan", "label_value": "Maker",
           "valid_until": "31 Dec 2027", "qr": "SW1:x", "standing": "valid"}


def save_space(actor, space, material):
    row = credential_service.space_row(space, create=True)
    return credential_service.save(actor, row, public_fields(material), scope="space", makerspace=space)


def save_platform(actor, material):
    row = credential_service.platform_row(create=True)
    return credential_service.save(actor, row, public_fields(material), scope="platform")


def deployment_files(settings, tmp_path, material, pass_type="pass.deploy"):
    for name, text in (("cert", material["apple_cert_pem"]), ("key", material["apple_key_pem"]),
                       ("wwdr", material["apple_wwdr_pem"])):
        (tmp_path / f"{name}.pem").write_text(text)
    settings.WALLET_APPLE_PASS_TYPE_ID, settings.WALLET_APPLE_TEAM_ID = pass_type, "TEAMDEPLOY1"
    settings.WALLET_APPLE_CERT_FILE = str(tmp_path / "cert.pem")
    settings.WALLET_APPLE_KEY_FILE = str(tmp_path / "key.pem")
    settings.WALLET_APPLE_WWDR_FILE = str(tmp_path / "wwdr.pem")


def test_off_without_any_credentials_for_either_platform():
    space, _manager = space_with_manager("t246-wallet-off")
    assert apple_for(space) is None and google_for(space) is None
    assert configured_platforms(space) == () and configured_platforms(None) == ()
    assert credential_service.describe_space(space)["effective"] == {"apple": None, "google": None}


def test_the_fallback_chain_is_space_then_platform_then_deployment_files(settings, tmp_path):
    space, manager = space_with_manager("t246-wallet-chain")
    deployment_files(settings, tmp_path, apple_material(pass_type="pass.deploy"))
    assert apple_for(space).source == "deployment" and apple_for(space).pass_type_id == "pass.deploy"
    save_platform(manager, apple_material(pass_type="pass.platform"))
    assert apple_for(space).source == "platform" and apple_for(None).source == "platform"
    save_space(manager, space, apple_material(pass_type="pass.space"))
    assert apple_for(space).source == "space" and apple_for(space).pass_type_id == "pass.space"
    row = credential_service.space_row(space)
    credential_service.save(manager, row, {"clear_apple": True}, scope="space", makerspace=space)
    assert apple_for(space).source == "platform"
    credential_service.save(manager, credential_service.platform_row(), {"clear_apple": True}, scope="platform")
    assert apple_for(space).source == "deployment"
    settings.WALLET_APPLE_PASS_TYPE_ID = ""
    assert apple_for(space) is None and configured_platforms(space) == ()


def test_apple_and_google_resolve_independently():
    space, manager = space_with_manager("t246-wallet-indep")
    save_platform(manager, apple_material())
    save_space(manager, space, google_material())
    assert apple_for(space).source == "platform" and google_for(space).source == "space"
    assert configured_platforms(space) == ("apple", "google")


def test_saving_the_same_material_twice_is_idempotent_and_a_new_certificate_is_a_rotation():
    space, manager = space_with_manager("t246-wallet-idem")
    material = apple_material(pass_type="pass.idem")
    save_space(manager, space, material)
    first = MakerspaceWalletCredentials.objects.get(makerspace=space).apple_cert_fingerprint
    save_space(manager, space, material)
    assert MakerspaceWalletCredentials.objects.filter(makerspace=space).count() == 1
    assert MakerspaceWalletCredentials.objects.get(makerspace=space).apple_cert_fingerprint == first
    actions = list(AuditLog.objects.filter(makerspace=space, action__startswith="wallet_pass.")
                   .order_by("pk").values_list("action", flat=True))
    assert actions == ["wallet_pass.credentials_saved", "wallet_pass.credentials_saved"]
    save_space(manager, space, apple_material(pass_type="pass.idem"))
    assert AuditLog.objects.filter(makerspace=space, action="wallet_pass.credentials_rotated").count() == 1
    assert all("BEGIN" not in str(row.meta) for row in AuditLog.objects.filter(makerspace=space))


def test_one_spaces_own_credentials_never_sign_or_show_in_another_space():
    space_a, manager_a = space_with_manager("t246-wallet-xa")
    space_b, _manager_b = space_with_manager("t246-wallet-xb")
    save_space(manager_a, space_a, apple_material(pass_type="pass.only-a"))
    assert apple_for(space_a).source == "space"
    assert apple_for(space_b) is None and configured_platforms(space_b) == ()
    fingerprint = MakerspaceWalletCredentials.objects.get(makerspace=space_a).apple_cert_fingerprint
    assert fingerprint not in json.dumps(credential_service.describe_space(space_b), default=str)
    assert not AuditLog.objects.filter(makerspace=space_b, action__startswith="wallet_pass.").exists()


def test_a_revoked_holder_gets_a_voided_pass_on_both_platforms_and_a_valid_one_is_not_voided():
    creds_mat = apple_material()
    from apps.card_designs.wallet.credentials import AppleCredentials
    creds = AppleCredentials(creds_mat["apple_pass_type_id"], creds_mat["apple_team_id"],
                             creds_mat["apple_cert_pem"].encode(), creds_mat["apple_key_pem"].encode(),
                             creds_mat["apple_wwdr_pem"].encode(), "test")
    assert json.loads(apple.pass_json(creds, "s1", {**CONTENT, "standing": "revoked"}))["voided"] is True
    assert not json.loads(apple.pass_json(creds, "s1", CONTENT)).get("voided")
    mat = google_material()
    account = json.loads(mat["google_service_account"])
    g = GoogleCredentials(mat["google_issuer_id"], "spaceworks_card", account["client_email"],
                          account["private_key"], "test")

    def state(link):
        body = link.rsplit(".", 2)[1]
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return claims["payload"]["genericObjects"][0]["state"]

    assert state(google.link_for(g, "s_1", CONTENT, voided=True)) == "INACTIVE"
    assert state(google.link_for(g, "s_1", CONTENT)) != "INACTIVE"


def test_a_pass_carries_no_contact_or_money_fields_even_if_the_content_offers_them():
    mat = apple_material()
    from apps.card_designs.wallet.credentials import AppleCredentials
    creds = AppleCredentials(mat["apple_pass_type_id"], mat["apple_team_id"], mat["apple_cert_pem"].encode(),
                             mat["apple_key_pem"].encode(), mat["apple_wwdr_pem"].encode(), "test")
    dirty = {**CONTENT, "email": "ada@example.org", "phone": "+919800000000", "balance": "INR 4,242",
             "amount_due": "999.99"}
    body = apple.pass_json(creds, "s1", dirty).decode()
    for leaked in ("ada@example.org", "+919800000000", "4,242", "999.99"):
        assert leaked not in body
