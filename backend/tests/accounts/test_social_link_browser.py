"""Linking GitHub/OIDC from a signed-in session: session-bound attempts that never sign anyone in."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import policy_for
from apps.accounts.models import OidcBrowserAttempt, User
from apps.accounts.models_social import SocialIdentity
from apps.audit.models import AuditLog
from tests.accounts.test_github_auth import CALLBACK, NONCE, ORIGIN, REDIRECT, configured, github  # noqa: F401
from tests.accounts.test_reauthentication import request as session_request

pytestmark = pytest.mark.django_db
LINK_START = "/api/v1/auth/social/github/link/authorize"
LINK_CALLBACK = "/api/v1/auth/social/link/callback"


def person(name="link-member", **extra):
    return User.objects.create_user(username=name, email=f"{name}@example.test", password="password",
                                    email_verified_at=timezone.now(), account_kind="member", **extra)


def signed_in(user, *, sid=None):
    client = APIClient()
    client.force_authenticate(user, token=session_request(user, sid=sid).auth)
    return client


def start(client):
    return client.post(LINK_START, {"redirect_uri": REDIRECT, "nonce": NONCE}, format="json", HTTP_ORIGIN=ORIGIN)


def finish(client, started):
    return client.post(LINK_CALLBACK, {"code": "github-code", "state": started.data["state"], "nonce": NONCE},
                       format="json", HTTP_ORIGIN=ORIGIN)


def test_signed_in_member_links_github_to_their_own_account(github):
    user = person()
    client = signed_in(user, sid="session:link-a")
    started = start(client)
    assert started.status_code == 200, started.data
    result = finish(client, started)
    assert result.status_code == 200, result.data
    assert result.data["provider"] == "github"
    assert SocialIdentity.objects.get(provider="github", provider_sub="1234567").user == user
    assert "access" not in result.data and "refresh_token" not in result.cookies
    assert AuditLog.objects.filter(action="auth.social_identity_linked", actor=user, meta__provider="github").exists()


def test_link_attempt_cannot_sign_in_and_sign_in_attempt_cannot_link(github):
    user = person()
    client = signed_in(user, sid="session:link-b")
    started = start(client)
    # The sign-in callback would mint a session; the session-bound digest never matches it.
    signed = APIClient().post(CALLBACK, {"code": "github-code", "state": started.data["state"], "nonce": NONCE},
                              format="json", HTTP_ORIGIN=ORIGIN)
    assert signed.status_code == 401
    assert not SocialIdentity.objects.exists()
    sign_in = APIClient().post("/api/v1/auth/social/github/authorize", {"redirect_uri": REDIRECT, "nonce": NONCE},
                               format="json", HTTP_ORIGIN=ORIGIN)
    assert finish(client, sign_in).status_code == 401
    assert not SocialIdentity.objects.exists()


def test_another_session_cannot_finish_the_link(github):
    user = person()
    started = start(signed_in(user, sid="session:link-c"))
    assert finish(signed_in(user, sid="session:link-d"), started).status_code == 401
    other = person("someone-else")
    assert finish(signed_in(other, sid="session:link-e"), started).status_code == 401
    assert not SocialIdentity.objects.exists()
    assert OidcBrowserAttempt.objects.get().consumed_at is not None  # spent, single-use


def test_identity_already_linked_elsewhere_is_refused(github):
    owner = person("github-owner")
    SocialIdentity.objects.create(user=owner, provider="github", provider_sub="1234567")
    user = person()
    client = signed_in(user, sid="session:link-f")
    result = finish(client, start(client))
    assert result.status_code == 409 and result.data["code"] == "identity_conflict"
    assert not SocialIdentity.objects.filter(user=user).exists()
    assert AuditLog.objects.filter(action="auth.social_identity_link_failed", actor=user,
                                   meta__reason="identity_conflict", meta__provider="github").exists()


def test_second_github_identity_is_refused(github):
    user = person()
    SocialIdentity.objects.create(user=user, provider="github", provider_sub="other-subject")
    client = signed_in(user, sid="session:link-g")
    result = finish(client, start(client))
    assert result.status_code == 409 and result.data["code"] == "provider_already_linked"


def test_platform_accounts_and_sessionless_tokens_are_refused_before_any_attempt(github):
    admin = User.objects.create_superuser(username="link-admin", email="link-admin@example.test", password="password",
                                          account_kind="platform", role="superadmin")
    assert start(signed_in(admin)).status_code == 403
    client = APIClient()
    client.force_authenticate(person())  # no session id to bind to
    assert start(client).status_code == 403
    assert APIClient().post(LINK_START, {"redirect_uri": REDIRECT, "nonce": NONCE}, format="json",
                            HTTP_ORIGIN=ORIGIN).status_code == 401
    assert not OidcBrowserAttempt.objects.exists()


def test_unknown_oidc_provider_is_404():
    client = signed_in(person(), sid="session:link-h")
    response = client.post("/api/v1/auth/social/oidc/nope/link/authorize", {"redirect_uri": REDIRECT},
                           format="json", HTTP_ORIGIN=ORIGIN)
    assert response.status_code == 404


def test_claim_sessions_are_refused_on_every_link_route():
    for name in ("social-github-link-start", "social-oidc-link-start", "social-link-callback"):
        assert isinstance(policy_for(name, "POST"), Refused)
