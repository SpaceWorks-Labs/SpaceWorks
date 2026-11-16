"""Decision 223(l): per-space and platform wallet-pass credentials (encrypted, write-only, audited)."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.card_designs.models import MakerspaceWalletCredentials, PlatformWalletCredentials
from apps.card_designs.wallet import credential_parsing as parsing
from apps.card_designs.wallet.credentials import apple_for, configured_platforms, google_for
from tests.accounts.reauth_helpers import force_recent_authenticate
from tests.l3_local.wallet_material import (
    apple_material, apple_p12, google_material, public_fields,
)
from tests.makerspaces.l4_helpers import features_off, features_on, space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _space(slug):
    makerspace, manager = space_with_manager(slug)
    makerspace.enabled_modules = sorted(set(makerspace.enabled_modules or []) | {"membership"})
    makerspace.save(update_fields=["enabled_modules"])
    features_on(makerspace, "wallet_passes")
    return makerspace, manager


def _superadmin():
    user = User.objects.create_user(username="wallet-root", password="Root password 77!", account_kind="platform",
                                    role=User.Role.SUPERADMIN, is_superuser=True, is_staff=True)
    client = APIClient()
    force_recent_authenticate(client, user)
    return client


def test_apple_material_is_validated_against_the_certificate():
    good = apple_material()
    parsed = parsing.parse_apple(public_fields(good), {})
    assert len(parsed["fingerprint"]) == 64 and parsed["expires_at"] > timezone.now()
    for patch, field in (({"apple_pass_type_id": "pass.other"}, "apple_pass_type_id"),
                         ({"apple_team_id": "WRONGTEAM1"}, "apple_team_id"),
                         ({"apple_key_pem": apple_material()["apple_key_pem"]}, "apple_key_pem")):
        with pytest.raises(ValidationError) as caught:
            parsing.parse_apple({**public_fields(good), **patch}, {})
        assert field in caught.value.detail


def test_an_expired_certificate_is_refused_and_a_p12_is_accepted():
    with pytest.raises(ValidationError) as caught:
        parsing.parse_apple(public_fields(apple_material(days=0)), {})
    assert "apple_cert_pem" in caught.value.detail
    material = apple_material()
    data = {"apple_p12": apple_p12(material), "apple_p12_password": "pw", "apple_pass_type_id": material["apple_pass_type_id"],
            "apple_team_id": material["apple_team_id"], "apple_wwdr_pem": material["apple_wwdr_pem"]}
    assert parsing.parse_apple(data, {})["pass_type_id"] == material["apple_pass_type_id"]
    with pytest.raises(ValidationError):
        parsing.parse_apple({**data, "apple_p12_password": "wrong"}, {})


def test_google_material_is_validated():
    good = google_material()
    assert len(parsing.parse_google(public_fields(good), {})["fingerprint"]) == 64
    for patch in ({"google_issuer_id": "not-a-number"}, {"google_service_account": "{not json"},
                  {"google_service_account": '{"client_email": "a@b.c", "private_key": "nope"}'},
                  {"google_class_prefix": "bad prefix!"}):
        with pytest.raises(ValidationError):
            parsing.parse_google({**public_fields(good), **patch}, {})


def test_space_credentials_win_over_platform_and_none_means_off():
    makerspace, manager = _space("wc-resolve")
    assert configured_platforms(makerspace) == () and apple_for(makerspace) is None
    client = _superadmin()
    platform = apple_material(pass_type="pass.platform")
    assert client.patch(reverse("admin-platform-wallet-credentials"), public_fields(platform), format="json").status_code == 200
    assert apple_for(makerspace).source == "platform" and configured_platforms(makerspace) == ("apple",)
    own = apple_material(pass_type="pass.space")
    response = authenticated_client(manager).patch(reverse("admin-wallet-credentials", args=[makerspace.pk]),
                                                   public_fields(own), format="json")
    assert response.status_code == 200 and response.json()["effective"] == {"apple": "space", "google": None}
    assert apple_for(makerspace).pass_type_id == "pass.space"
    assert apple_for(None).pass_type_id == "pass.platform"


def test_secrets_are_never_returned_and_are_encrypted_at_rest():
    makerspace, manager = _space("wc-secret")
    material = {**public_fields(apple_material()), **public_fields(google_material())}
    client = authenticated_client(manager)
    url = reverse("admin-wallet-credentials", args=[makerspace.pk])
    saved = client.patch(url, material, format="json")
    assert saved.status_code == 200
    for response in (saved, client.get(url)):
        text = response.content.decode()
        assert "BEGIN" not in text and "private_key" not in text and "gserviceaccount" not in text
        body = response.json()
        assert body["apple"]["configured"] and len(body["apple"]["fingerprint"]) == 64 and body["apple"]["expires_at"]
        assert body["google"]["configured"] and body["google"]["issuer_id"] == material["google_issuer_id"]
    row = MakerspaceWalletCredentials.objects.get(makerspace=makerspace)
    for stored in (row.apple_cert_pem, row.apple_key_pem, row.apple_wwdr_pem, row.google_service_account):
        assert stored.startswith("fernet:") and "BEGIN" not in stored


def test_save_rotate_and_remove_are_each_audited_without_secrets():
    makerspace, manager = _space("wc-audit")
    client = authenticated_client(manager)
    url = reverse("admin-wallet-credentials", args=[makerspace.pk])
    first = public_fields(apple_material())
    client.patch(url, first, format="json")
    client.patch(url, {"apple_team_id": first["apple_team_id"]}, format="json")
    client.patch(url, public_fields(apple_material()), format="json")
    client.patch(url, {"clear_apple": True}, format="json")
    actions = list(AuditLog.objects.filter(action__startswith="wallet_pass.credentials").order_by("id")
                   .values_list("action", flat=True))
    assert actions == ["wallet_pass.credentials_saved", "wallet_pass.credentials_saved",
                       "wallet_pass.credentials_rotated", "wallet_pass.credentials_removed"]
    for row in AuditLog.objects.filter(action__startswith="wallet_pass.credentials"):
        assert "BEGIN" not in str(row.meta) and set(row.meta) <= {"scope", "platform", "fingerprint"}
    assert client.get(url).json()["apple"]["configured"] is False


def test_the_space_route_needs_the_capability_and_a_manager():
    makerspace, manager = _space("wc-gate")
    other, other_manager = _space("wc-gate-other")
    url = reverse("admin-wallet-credentials", args=[makerspace.pk])
    assert authenticated_client(other_manager).get(url).status_code in (403, 404)
    features_off(makerspace, "wallet_passes")
    assert authenticated_client(manager).get(url).status_code == 404
    assert other.pk != makerspace.pk


def test_platform_credentials_are_superadmin_only_and_audited():
    makerspace, manager = _space("wc-platform")
    url = reverse("admin-platform-wallet-credentials")
    assert authenticated_client(manager).get(url).status_code in (401, 403)
    client = _superadmin()
    assert client.get(url).json()["apple"]["configured"] is False
    assert client.patch(url, public_fields(google_material()), format="json").status_code == 200
    assert PlatformWalletCredentials.objects.get(pk=1).google_complete
    assert google_for(makerspace).source == "platform"
    audit = AuditLog.objects.get(action="wallet_pass.credentials_saved")
    assert audit.meta["scope"] == "platform" and audit.meta["platform"] == "google"


def test_credentials_are_omitted_from_exports_and_tenant_moves():
    from apps.data_export.classification import OMITTED_MODELS
    from apps.tenant_migration.catalog_l3 import PROJECTED_LABELS
    for label in ("card_designs.MakerspaceWalletCredentials", "card_designs.PlatformWalletCredentials"):
        assert label in OMITTED_MODELS and label not in PROJECTED_LABELS


def test_platform_fallback_applies_on_every_install(settings):
    """Decision 240: space credentials, else platform, else deployment files, whatever the hosting switch says."""
    makerspace, _manager = _space("wc-hosting-off")
    assert _superadmin().patch(reverse("admin-platform-wallet-credentials"), public_fields(apple_material()),
                               format="json").status_code == 200
    assert apple_for(makerspace).source == "platform"
    settings.MANAGED_PLANS_ENABLED = False
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    assert apple_for(makerspace).source == "platform" and configured_platforms(makerspace) == ("apple",)
    assert apple_for(None).source == "platform"


def test_expired_or_undecryptable_space_credentials_fall_back(monkeypatch):
    makerspace, manager = _space("wc-broken")
    client = _superadmin()
    client.patch(reverse("admin-platform-wallet-credentials"), public_fields(apple_material(pass_type="pass.platform")),
                 format="json")
    authenticated_client(manager).patch(reverse("admin-wallet-credentials", args=[makerspace.pk]),
                                        public_fields(apple_material(pass_type="pass.space")), format="json")
    assert apple_for(makerspace).source == "space"
    MakerspaceWalletCredentials.objects.filter(makerspace=makerspace).update(
        apple_cert_expires_at=timezone.now() - timedelta(days=1))
    assert apple_for(makerspace).source == "platform"
    MakerspaceWalletCredentials.objects.filter(makerspace=makerspace).update(
        apple_cert_expires_at=None, google_issuer_id="3388000000012345678", google_service_account="fernet:garbage")
    from apps.card_designs.wallet import credentials
    assert credentials.google_for(makerspace) is None  # a bad ciphertext reads as "not configured", not a 500
