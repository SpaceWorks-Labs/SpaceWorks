"""OIDC-only event staff use the normal browser flow, authority checks and MFA."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import OidcBrowserAttempt, User
from apps.accounts.models_mfa import MFAChallenge
from apps.accounts.models_social import SocialIdentity
from apps.events.services_staff_grants import revoke_grant
from tests.accounts.oidc_browser_helpers import make_provider, metadata
from django.utils import timezone

from apps.accounts.mfa_crypto import totp
from tests.accounts.mfa_helpers import enrolled
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.test_staff_grant_auth import PLATFORM_ORIGIN, staff_origin
from tests.events.ticketing_helpers import event_space

pytestmark = pytest.mark.django_db
START = "/api/v1/auth/social/oidc/campus/authorize"
CALLBACK = "/api/v1/auth/social/oidc/callback"


@pytest.fixture
def oidc_staff(monkeypatch, settings):
    space, manager, user, event, grant = grant_fixture()
    user.set_unusable_password()
    user.save(update_fields=["password"])
    provider = make_provider()
    SocialIdentity.objects.create(user=user, provider=provider.provider_key, provider_sub="invitee-sub")
    settings.PLATFORM_STAFF_ORIGINS = [PLATFORM_ORIGIN]
    settings.CORS_ALLOWED_ORIGINS = ["https://member-only.example.test"]
    monkeypatch.setattr("apps.accounts.views_oidc_browser.discover", lambda _: metadata(provider))
    monkeypatch.setattr("apps.accounts.views_oidc_browser.exchange_code", lambda *a, **k: "id-token")
    monkeypatch.setattr("apps.accounts.views_oidc_browser.verify_oidc_token", lambda *a, **k: {
        "sub": "invitee-sub", "email": user.email, "email_verified": True,
    })
    return space, manager, user, event, grant


def start(origin=PLATFORM_ORIGIN, surface="member"):
    return APIClient().post(START, {
        "redirect_uri": f"{origin}/admin/assigned-events", "surface": surface,
    }, format="json", HTTP_ORIGIN=origin)


def finish(started, origin=PLATFORM_ORIGIN, **extra):
    return APIClient().post(CALLBACK, {
        "code": "code", "state": started.data["state"], "nonce": started.data["nonce"], **extra,
    }, format="json", HTTP_ORIGIN=origin)


@pytest.mark.parametrize("scope", ["platform", "own", "other"])
def test_oidc_member_grantee_actions_require_authorized_origin(oidc_staff, scope):
    space, _, user, event, _ = oidc_staff
    origin = PLATFORM_ORIGIN if scope == "platform" else staff_origin(
        space if scope == "own" else event_space("oidc-other-origin")
    )
    started = start(origin)
    assert started.status_code == 200, started.data
    assert OidcBrowserAttempt.objects.get().surface == "member"
    response = finish(started, origin)
    assert response.status_code == 200, response.data
    assert not user.has_usable_password()
    token = RefreshToken(response.cookies["refresh_token"].value)
    assert token["surface"] == "member" and token["kind"] == "person"
    assert response.data["user"]["makerspaces"] == []
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    detail = client.get(reverse("admin-event-detail", args=[event.pk]), HTTP_ORIGIN=origin)
    assert detail.status_code == (403 if scope == "other" else 200), detail.data
    assert finish(started, origin).status_code == 401


def test_member_oidc_attempt_cannot_be_promoted_by_callback_fields(oidc_staff):
    _, _, _, event, _ = oidc_staff
    started = start(surface="member")
    response = finish(started, surface="staff")
    assert response.status_code == 200, response.data
    assert RefreshToken(response.cookies["refresh_token"].value)["surface"] == "member"
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get(reverse("admin-event-detail", args=[event.pk]), HTTP_ORIGIN=PLATFORM_ORIGIN).status_code == 200


def test_staff_oidc_surface_is_refused_even_on_trusted_origin(oidc_staff):
    response = start("https://member-only.example.test", surface="staff")
    assert response.status_code == 403
    assert not OidcBrowserAttempt.objects.exists()


def test_member_oidc_actions_recheck_grant_after_callback(oidc_staff):
    _, manager, _, event, grant = oidc_staff
    started = start()
    revoke_grant(grant, actor=manager)
    response = finish(started)
    assert response.status_code == 200, response.data
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get(reverse("admin-event-detail", args=[event.pk]), HTTP_ORIGIN=PLATFORM_ORIGIN).status_code == 403


def test_staff_oidc_does_not_create_unknown_accounts(oidc_staff, monkeypatch):
    monkeypatch.setattr("apps.accounts.views_oidc_browser.verify_oidc_token", lambda *a, **k: {
        "sub": "unknown-sub", "email": "unknown@example.test", "email_verified": True,
    })
    response = start(surface="staff")
    assert response.status_code == 403
    assert not User.objects.filter(email="unknown@example.test").exists()
    assert not SocialIdentity.objects.filter(provider_sub="unknown-sub").exists()


def test_staff_oidc_refuses_disabled_tenant_and_inactive_account(oidc_staff):
    space, _, user, event, _ = oidc_staff
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert finish(start()).status_code == 403
    user.is_active = True
    user.save(update_fields=["is_active"])
    space.enabled_modules = [key for key in space.enabled_modules if key != "events"]
    space.save(update_fields=["enabled_modules"])
    response = finish(start())
    assert response.status_code == 200, response.data
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    assert client.get(reverse("admin-event-detail", args=[event.pk]), HTTP_ORIGIN=PLATFORM_ORIGIN).status_code == 403


def test_member_oidc_mfa_challenge_retains_member_kind(oidc_staff):
    # Decision 62: staff MFA is a platform rule (the per-space switch is retired), so a grant holder who
    # HAS enrolled a factor proves it at every sign-in; an unenrolled one still gets a member session.
    space, _, user, _, _ = oidc_staff
    _, secret = enrolled(user)
    origin = staff_origin(space)
    response = finish(start(origin), origin)
    assert response.status_code == 200, response.data
    assert response.data["mfa_required"] and not response.data["enrollment_required"]
    assert "access" not in response.data and "refresh_token" not in response.cookies
    challenge = MFAChallenge.objects.get(user=user)
    assert challenge.context["surface"] == "member"
    assert challenge.context["kind"] == "person"
    assert challenge.context["makerspace"] is None
    assert challenge.context["origin"] == origin
    code = totp(secret, int(timezone.now().timestamp() // 30))
    completed = APIClient().post("/api/v1/auth/mfa/verify", {"challenge": response.data["challenge"], "code": code},
                                 format="json", HTTP_ORIGIN=origin)
    assert completed.status_code == 200, completed.data
    token = RefreshToken(completed.cookies["refresh_token"].value)
    assert token["surface"] == "member" and token["kind"] == "person"
