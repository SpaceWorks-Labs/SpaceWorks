"""Native staff is a step-up grant on the person: fixed tenant, MFA and attestation (U-A2)."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.accounts.attestation import VerifiedAttestation
from apps.accounts.mfa_crypto import totp
from apps.accounts.models import DeviceGrant, User
from apps.makerspaces.models import MakerspaceMembership
from tests.accounts.account_factories import make_staff, make_membership
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.native_helpers_m1d import attested_login, attested_staff_login, configure_native_social
from tests.accounts.test_social_first_grant import complete_login, issue_challenge, mock_identity, request_nonce
from tests.fixed_roles.helpers import assign_builtin_roles
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db
PASSWORD = "strong-device-password"
ME = "/api/v1/auth/me"
REFRESH = "/api/v1/auth/device/refresh"


def inventory(space):
    return f"/api/v1/admin/makerspace/{space.pk}/inventory"


def bearer(access):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return client


@pytest.fixture
def staff():
    space = make_space("native-staff-m1a")
    return make_staff(space, username="native-staff-m1a", role_slug="inventory_manager",
                      password=PASSWORD, email="native-staff@example.test"), space


@pytest.mark.parametrize("kind", ["member", "staff"])
def test_password_grant_and_me_expose_server_owned_authority(settings, monkeypatch, kind):
    space = make_space("native-password-authority")
    if kind == "staff":
        user = make_staff(space, username="native-password-authority", role_slug="inventory_manager", password=PASSWORD)
        login, _ = attested_staff_login(APIClient(), user, settings, monkeypatch)
    else:
        user = make_user("native-password-authority", password=PASSWORD)
        make_membership(user, space)
        login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200
    grant = DeviceGrant.objects.get(pk=login.data["device_grant"]["id"])
    assert grant.authority == kind
    assert grant.staff_makerspace_id == (space.pk if kind == "staff" else None)
    claims = AccessToken(login.data["access"])
    assert claims["kind"] == "person" and "makerspace" not in claims.payload
    assert claims["surface"] == "member"
    me = bearer(login.data["access"]).get(ME)
    assert me.status_code == 200
    assert me.data["session_authority"] == ("native_staff" if kind == "staff" else "member")


def test_staff_path_requires_fixed_tenant_and_live_membership(settings, monkeypatch, staff):
    user, space = staff
    other = make_space("native-other-local")
    login, _ = attested_staff_login(APIClient(), user, settings, monkeypatch)
    client = bearer(login.data["access"])
    assert client.get(inventory(space)).status_code == 403
    headers = {"HTTP_X_MAKERSPACE_ID": str(space.pk)}
    assert client.get(inventory(space), **headers).status_code == 200
    assert client.get(inventory(other), **headers).status_code == 403
    assert client.get(inventory(other), HTTP_X_MAKERSPACE_ID=str(other.pk)).status_code == 403
    MakerspaceMembership.staff_tracks.filter(user=user, makerspace=space).update(status="revoked")
    assert client.get(inventory(space), **headers).status_code in {401, 403}


def test_member_grant_cannot_forge_staff_context(settings, monkeypatch):
    space = make_space("native-member-staff-denied")
    user = make_user("native-member-staff-denied", password=PASSWORD)
    make_membership(user, space)
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    client = bearer(login.data["access"])
    assert client.get(inventory(space), HTTP_X_MAKERSPACE_ID=str(space.pk)).status_code == 403
    forged = AccessToken(login.data["access"])
    forged["surface"] = "staff_api"
    assert bearer(str(forged)).get(inventory(space), HTTP_X_MAKERSPACE_ID=str(space.pk)).status_code == 401


def test_staff_authority_and_credential_snapshot_survive_refresh(settings, monkeypatch, staff):
    user, space = staff
    login, _ = attested_staff_login(APIClient(), user, settings, monkeypatch)
    rotated = APIClient().post(REFRESH, {"refresh": login.data["refresh"]}, format="json")
    assert rotated.status_code == 200 and rotated.data["refresh"] != login.data["refresh"]
    claims = AccessToken(rotated.data["access"])
    assert claims["surface"] == "member" and "makerspace" not in claims.payload
    assert claims["credential_generation"] == user.credential_generation
    assert bearer(rotated.data["access"]).get(inventory(space), HTTP_X_MAKERSPACE_ID=str(space.pk)).status_code == 200


def test_password_mfa_preserves_staff_provenance_and_attestation_metadata(settings, monkeypatch, staff):
    user, space = staff
    _, secret = enrolled(user)
    metadata = {"key_id": "attested-key", "public_key": "attested-public-key"}
    monkeypatch.setattr("apps.accounts.views_device.verify_attestation",
                        lambda *args: VerifiedAttestation("device-subject", metadata))
    first, _ = attested_login(APIClient(), user, settings, monkeypatch, staff_space=space)
    assert first.status_code == 200 and first.data["mfa_required"] and "access" not in first.data
    assert not DeviceGrant.objects.filter(user=user).exists()
    completed = APIClient().post("/api/v1/auth/mfa/verify", {
        "challenge": first.data["challenge"], "code": totp(secret, int(timezone.now().timestamp() // 30)),
    }, format="json")
    assert completed.status_code == 200
    grant = DeviceGrant.objects.get(user=user)
    assert grant.authority == "staff" and grant.login_method == "password"
    assert grant.staff_makerspace_id == space.pk
    assert grant.attestation_key_id == metadata["key_id"]
    assert grant.attestation_public_key == metadata["public_key"]
    assert AccessToken(completed.data["access"])["surface"] == "member"
    assert completed.data["user"]["session_authority"] == "native_staff"


def test_social_first_grant_resolves_member_sharing_staff_email(settings, monkeypatch, staff):
    staff_user, space = staff
    member = User.objects.create_user(username="native-member-same-contact", password=PASSWORD,
                                     email="native-member-other@example.test",
                                     email_verified_at=timezone.now())  # one email per person (R2)
    configure_native_social(settings)
    challenge = issue_challenge(APIClient())
    nonce = request_nonce(APIClient(), challenge)
    assert nonce.status_code == 200
    mock_identity(monkeypatch, member)
    from tests.accounts.native_helpers_m1d import mock_attestation
    mock_attestation(monkeypatch, challenge)
    result = complete_login(APIClient(), nonce.data["nonce"], challenge)
    assert result.status_code == 200
    grant = DeviceGrant.objects.get(user=member)
    assert grant.authority == "member" and grant.staff_makerspace_id is None
    assert not DeviceGrant.objects.filter(user=staff_user).exists()
    assert result.data["user"]["id"] == member.pk
    assert result.data["user"]["makerspaces"] == []


def test_member_device_can_read_personal_notifications_only(settings, monkeypatch):
    space = make_space("native-personal-notifications")
    space.enabled_features = sorted(set(space.enabled_features) | {
        "notifications.member_inbox", "notifications.member_preferences",
        "membership.broadcasts",
    })
    space.save(update_fields=["enabled_features"])
    user = make_user("native-notification-member", password="strong-device-password")
    assign_builtin_roles(user, space, "member")
    login, _ = attested_login(APIClient(), user, settings, monkeypatch)
    assert login.status_code == 200
    client = bearer(login.data["access"])
    for path in ("inbox", "preferences", "announcements"):
        assert client.get(f"/api/v1/notifications/{path}/{space.pk}").status_code == 200
    for path in ("broadcasts", "makerspace"):
        assert client.get(f"/api/v1/notifications/{path}/{space.pk}").status_code == 403
