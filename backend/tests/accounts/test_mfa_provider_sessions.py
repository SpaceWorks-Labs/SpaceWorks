"""Identity-provider proof survives refresh, but never survives credential revocation."""

import uuid

import pytest
from cryptography.fernet import Fernet
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import UntypedToken

from apps.accounts import mfa_policy
from apps.accounts.models import User
from apps.accounts.models_social import SocialIdentity
from apps.accounts.services_mfa import change
from apps.accounts.models_mfa import UserMFA
from apps.accounts.tokens import SpaceWorksRefreshToken
from tests.accounts.mfa_helpers import enrolled
from tests.accounts.test_mfa_platform_switch import PASSWORD, require_staff, web_refresh
from tests.accounts.test_social_auth import configure_google, login, mock_claims, nonce
from tests.accounts.test_social_first_grant import (
    complete_login, configure_native_social, issue_challenge, mock_attestation,
    request_nonce,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def encryption(settings):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    settings.CORS_ALLOWED_ORIGINS = ["http://localhost:5000", "http://localhost:5173"]


def google_login(user, monkeypatch, source="provider"):
    configure_google()
    SocialIdentity.objects.create(user=user, provider="google", provider_sub="provider-proof")
    mock_claims(monkeypatch, sub="provider-proof", email=user.email)
    client = APIClient()
    first = nonce(client)
    assert first.status_code == 200
    result = login(client, first.data["nonce"])
    assert result.status_code == 200 and "challenge" not in result.data
    assert UntypedToken(result.data["access"])["mfa_source"] == source
    return client, result


def test_enrolled_staff_provider_proof_never_mints_a_session(monkeypatch):
    """#62: provider proof stands in only for people MFA is not mandatory for; S-B's door
    challenges enrolled staff after the provider and mints nothing until auth/mfa/verify."""
    user = User.objects.create_user(username="provider-staff-mfa", email="pmfa@example.test", password=PASSWORD)
    require_staff(user)
    enrolled(user)
    configure_google()
    SocialIdentity.objects.create(user=user, provider="google", provider_sub="provider-proof")
    mock_claims(monkeypatch, sub="provider-proof", email=user.email)
    client = APIClient()
    response = login(client, nonce(client).data["nonce"])
    assert response.status_code == 200 and response.data["mfa_required"] is True, response.data
    assert "access" not in response.data and "totp" in response.data["factors"]


def test_unenrolled_staff_google_web_and_native_refresh_never_get_provider_proof(settings, monkeypatch):
    """S-B (#62): an IdP never stands in for a staff factor. Unenrolled staff (in their grace)
    sign in with `mfa_source=none`, on web and native, and refresh keeps it so."""
    user = User.objects.create_user(username="provider-staff", email="provider@example.test", password=PASSWORD)
    require_staff(user)
    client, signed_in = google_login(user, monkeypatch, source="none")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {signed_in.data['access']}")
    assert client.get("/api/v1/auth/me").status_code == 200
    client.credentials()
    refreshed = web_refresh(client)
    assert refreshed.status_code == 200
    assert UntypedToken(refreshed.data["access"])["mfa_source"] == "none"

    # First native provider sign-in has no pre-existing grant or local MFA proof.
    configure_native_social(settings)
    raw = issue_challenge(APIClient())
    proof = request_nonce(APIClient(), raw)
    assert proof.status_code == 200
    mock_claims(monkeypatch, sub="provider-proof", email=user.email)
    mock_attestation(monkeypatch, raw)
    native = complete_login(APIClient(), proof.data["nonce"], raw)
    assert native.status_code == 200 and "challenge" not in native.data
    rotated = APIClient().post("/api/v1/auth/device/refresh", {
        "refresh": native.data["refresh"]}, format="json")
    assert rotated.status_code == 200
    assert UntypedToken(rotated.data["access"])["mfa_source"] == "none"
    assert UntypedToken(rotated.data["refresh"])["mfa_source"] == "none"
    password = APIClient().post("/api/v1/auth/login", {
        "username": user.username, "password": PASSWORD, "surface": "member"}, format="json")
    # No factor yet: a member session plus the grace banner, never a forced enrolment (#128 C-1).
    assert password.status_code == 200 and password.data["user"]["mfa_enrolment_due"] is True


@pytest.mark.parametrize("operation", ["reset", "disable"])
def test_provider_access_and_refresh_are_revoked_by_mfa_changes(operation, monkeypatch):
    user = User.objects.create_user(username="provider-member", email="member@example.test", password=PASSWORD)
    enrolled(user)
    client, response = google_login(user, monkeypatch)
    assert web_refresh(client).status_code == 200
    if operation == "reset":
        # A credential-version reset invalidates provider proof for this member.
        row = UserMFA.objects.get(user=user)
        row.version = uuid.uuid4()
        row.save(update_fields=["version"])
    else:
        change(user, PASSWORD, disable=True)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get("/api/v1/auth/me").status_code == 401
    client.credentials()
    assert web_refresh(client).status_code == 401


def test_provider_claim_never_overrides_a_mismatched_credential_version():
    user = User.objects.create_user(username="version-proof", password=PASSWORD)
    row, _ = enrolled(user)
    with pytest.raises(AuthenticationFailed):
        mfa_policy.assert_verified(user, {"mfa_source": "provider", "mfa_version": str(uuid.uuid4())})
    mfa_policy.assert_verified(user, {"mfa_source": "provider", "mfa_version": str(row.version)})
    # Legacy tokens retain the pre-source-claim version semantics.
    mfa_policy.assert_verified(user, {"mfa_version": str(row.version)})


def test_verified_and_none_sources_describe_actual_password_proof():
    user = User.objects.create_user(username="local-proof", password=PASSWORD)
    assert SpaceWorksRefreshToken.for_user(user)["mfa_source"] == "none"
    row, _ = enrolled(user)
    mfa_policy.stamp(user, row)
    assert SpaceWorksRefreshToken.for_user(user)["mfa_source"] == "verified"
