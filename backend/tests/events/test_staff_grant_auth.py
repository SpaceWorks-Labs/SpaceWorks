from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts import mfa_policy, rbac
from apps.accounts.serializers_payload import user_payload
from apps.accounts.serializers_refresh import SpaceWorksTokenRefreshSerializer
from apps.accounts.services_social_identity import SocialResolutionError
from apps.accounts.services_social_login import assert_staff_authority
from apps.events.services_staff_grants import revoke_grant
from tests.accounts.test_social_auth import configure_google, login, mock_claims, nonce
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import event_space

pytestmark = pytest.mark.django_db
PLATFORM_ORIGIN = "https://platform-staff.example.test"


def staff_origin(space):
    space.frontend_domain = f"{space.slug}.example.test"
    space.frontend_domain_status = "verified"
    space.save(update_fields=["frontend_domain", "frontend_domain_status"])
    return f"https://{space.frontend_domain}"


@pytest.mark.parametrize("scope", ["platform", "own", "other"])
def test_password_sign_in_is_scoped_for_grant_only_accounts(settings, scope):
    space, _, user, event, _ = grant_fixture()
    settings.PLATFORM_STAFF_ORIGINS = [PLATFORM_ORIGIN]
    origin = PLATFORM_ORIGIN if scope == "platform" else staff_origin(
        space if scope == "own" else event_space("other-staff-origin")
    )
    response = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "staff-grant-password-123", "surface": "delegated",
    }, format="json", HTTP_ORIGIN=origin)
    assert response.status_code == 200, response.data
    refresh = RefreshToken(response.cookies["refresh_token"].value)
    assert refresh["surface"] == "delegated" and refresh["kind"] == "member"
    assert response.data["user"]["makerspaces"] == []
    assert not rbac.effective_actions(user, space.pk)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    detail = client.get(reverse("admin-event-detail", args=[event.pk]), HTTP_ORIGIN=origin)
    assert detail.status_code == (403 if scope == "other" else 200), detail.data


def test_originless_member_sign_in_revoked_grant_cannot_reach_event():
    _, manager, user, event, grant = grant_fixture()
    client = APIClient()
    data = {"username": user.username, "password": "staff-grant-password-123", "surface": "delegated"}
    assert client.post(reverse("auth-login"), data, format="json").status_code == 200
    revoke_grant(grant, actor=manager)
    response = client.post(reverse("auth-login"), data, format="json")
    assert response.status_code == 200, response.data
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get(reverse("admin-event-detail", args=[event.pk])).status_code == 403


def test_forced_password_rotation_grant_holder_can_sign_in_and_rotate_only():
    _, _, user, event, _ = grant_fixture()
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    signed_in = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "staff-grant-password-123", "surface": "delegated",
    }, format="json")
    assert signed_in.status_code == 200, signed_in.data
    assert RefreshToken(signed_in.cookies["refresh_token"].value)["surface"] == "delegated"
    assert signed_in.data["user"]["must_change_password"] is True
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {signed_in.data['access']}")
    assert client.get(reverse("admin-event-detail", args=[event.pk])).status_code == 403
    rotated = client.post(reverse("auth-change-password"), {
        "current_password": "staff-grant-password-123", "new_password": "A fresh event credential 901!",
    }, format="json")
    assert rotated.status_code == 200, rotated.data
    user.refresh_from_db()
    assert user.must_change_password is False


@pytest.mark.parametrize("scope", ["platform", "own", "other"])
def test_social_sign_in_accepts_only_grants_in_staff_origin_scope(monkeypatch, settings, scope):
    space, _, user, event, _ = grant_fixture()
    settings.PLATFORM_STAFF_ORIGINS = [PLATFORM_ORIGIN]
    # Consumer sign-in belongs to the member-account ecosystem (D5/D8).
    space.enabled_modules = sorted(set(space.enabled_modules) | {"member_accounts"})
    space.save(update_fields=["enabled_modules"])
    configure_google()
    mock_claims(monkeypatch, email=user.email, sub="event-grant-social")
    origin = PLATFORM_ORIGIN if scope == "platform" else staff_origin(
        space if scope == "own" else event_space("social-wrong-origin")
    )
    challenge = nonce(APIClient(), origin=origin)
    assert challenge.status_code == 200, challenge.data
    response = login(APIClient(), challenge.data["nonce"], origin=origin)
    assert response.status_code == 200, response.data
    assert RefreshToken(response.cookies["refresh_token"].value)["surface"] == "member"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    detail = client.get(reverse("admin-event-detail", args=[event.pk]), HTTP_ORIGIN=origin)
    assert detail.status_code == (403 if scope == "other" else 200), detail.data


def test_staff_authority_discovery_and_payload_do_not_escape_selected_space():
    space, _, user, event, _ = grant_fixture()
    scoped = SimpleNamespace(headers={}, selected_makerspace_id=space.pk)
    assert_staff_authority(user, scoped)
    payload = user_payload(user, request=scoped)
    assert payload["makerspaces"] == []
    assert payload["event_grants"][0]["permissions"] == ["edit_details"]
    assert payload["event_grants"][0]["event_id"] == event.pk
    foreign = SimpleNamespace(headers={}, selected_makerspace_id=event_space("auth-foreign").pk)
    with pytest.raises(SocialResolutionError):
        assert_staff_authority(user, foreign)
    assert user_payload(user, request=foreign)["event_grants"] == []


def test_member_refresh_keeps_session_but_actions_revalidate_grant(settings):
    space, manager, user, event, grant = grant_fixture()
    origin = staff_origin(space)
    response = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "staff-grant-password-123", "surface": "delegated",
    }, format="json", HTTP_ORIGIN=origin)
    assert response.status_code == 200, response.data
    refresh = response.cookies["refresh_token"].value
    revoke_grant(grant, actor=manager)
    rotated = SpaceWorksTokenRefreshSerializer().validate({"refresh": refresh})
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {rotated['access']}")
    assert client.get(reverse("admin-event-detail", args=[event.pk]), HTTP_ORIGIN=origin).status_code == 403


def test_mfa_policy_counts_grant_staff_without_granting_tenant_actions():
    space, manager, user, _, grant = grant_fixture()
    assert not mfa_policy.required(user)
    space.enabled_features = [*space.enabled_features, "security.staff_mfa_required"]
    # Security keys change only through the security service; write the fixture row directly.
    type(space).objects.filter(pk=space.pk).update(enabled_features=space.enabled_features)
    assert mfa_policy.required(user)
    assert not rbac.effective_actions(user, space.pk)
    response = APIClient().post(reverse("auth-login"), {
        "username": user.username, "password": "staff-grant-password-123", "surface": "delegated",
    }, format="json")
    assert response.status_code == 200 and response.data["enrollment_required"]
    assert "access" not in response.data
    revoke_grant(grant, actor=manager)
    assert not mfa_policy.required(user)


def test_phone_member_session_cannot_promote_itself_using_an_event_grant(monkeypatch):
    _, _, user, event, _ = grant_fixture()
    monkeypatch.setattr("apps.accounts.views_phone._phone_login_available", lambda: True)
    monkeypatch.setattr("apps.accounts.views_phone.confirm_login", lambda *args: user)
    response = APIClient().post(reverse("auth-phone-login-confirm"), {
        "phone": "+14155552671", "code": "123456", "surface": "delegated",
    }, format="json")
    # Caller fields cannot mint staff credentials; the member session still has
    # its live, narrowly granted event access under V1/V8.
    assert response.status_code == 200, response.data
    assert RefreshToken(response.cookies["refresh_token"].value)["surface"] == "member"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get(reverse("admin-event-detail", args=[event.pk])).status_code == 200
