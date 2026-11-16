"""GitHub OAuth protocol, secret redaction and member/staff lockout boundaries."""

import base64
import gzip
import hashlib
import json
from datetime import timedelta
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from cryptography.fernet import Fernet
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps.accounts.admin_social import PlatformLoginMethodsForm, PlatformSocialAuthSettingsForm
from apps.accounts.claim_route_types import Refused
from apps.accounts.claim_routes import policy_for
from apps.accounts.models import OidcBrowserAttempt, User
from apps.accounts.models_login_methods import PlatformLoginMethods
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from apps.accounts.services_social_identity import SocialResolutionError, unlink_social_identity
from apps.admin_api.views_platform_social import PlatformSocialAuthSettingsSerializer
from apps.audit.models import AuditLog
from tests.accounts.mfa_helpers import enrolled

pytestmark = pytest.mark.django_db
ORIGIN = "http://localhost:5000"
REDIRECT = f"{ORIGIN}/member"
START = "/api/v1/auth/social/github/authorize"
CALLBACK = "/api/v1/auth/social/github/callback"
SETTINGS = "/api/v1/admin/platform/social-auth-settings"
SECRET = "github-client-secret-never-publish"
TOKEN = "github-access-token-never-publish"
NONCE = "browser-random-nonce-" + "a" * 43


class RawBody(BytesIO):
    """urllib3-like raw stream: decode_content undoes the declared gzip encoding."""

    def __init__(self, body, gzipped):
        super().__init__(body)
        self.gzipped = gzipped

    def read(self, amt=-1, decode_content=False):
        if self.gzipped and decode_content:
            return gzip.decompress(super().read())[:amt]
        return super().read(amt)


class JsonResponse:
    def __init__(self, payload, status=200, *, body=None, headers=None, gzipped=False):
        body = json.dumps(payload).encode() if body is None else body
        if gzipped:
            body = gzip.compress(body)
        self.raw = RawBody(body, gzipped)
        self.headers = headers or {"Content-Length": str(len(body))}
        self.status_code = status

    def close(self):
        self.raw.close()


@pytest.fixture(autouse=True)
def configured(settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    settings.AUTH_COOKIE_SECURE = False
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    cache.clear()
    row = PlatformSocialAuthSettings.load()
    row.github_client_id = "github-oauth-client"
    row.set_github_client_secret(SECRET)
    row.save()
    return row


@pytest.fixture
def github(monkeypatch):
    emails = [{"email": "primary@example.test", "primary": True, "verified": True}]
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        assert url == "https://github.com/login/oauth/access_token"
        assert kwargs["headers"]["Accept"] == "application/json"
        assert kwargs["data"]["client_secret"] == SECRET
        assert kwargs["data"]["redirect_uri"] == REDIRECT
        assert kwargs["data"]["code_verifier"] == OidcBrowserAttempt.objects.get().code_verifier
        assert kwargs["timeout"] and kwargs["allow_redirects"] is False
        return JsonResponse({"access_token": TOKEN, "token_type": "bearer"})

    def get(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"
        assert kwargs["headers"]["Accept"] == "application/vnd.github+json"
        assert kwargs["headers"]["X-GitHub-Api-Version"] == "2022-11-28"
        assert kwargs["timeout"] and kwargs["allow_redirects"] is False
        if url == "https://api.github.com/user":
            return JsonResponse({"id": 1234567, "name": "GitHub Member", "email": "ignored@example.test"})
        assert url == "https://api.github.com/user/emails"
        return JsonResponse(emails)

    monkeypatch.setattr("apps.accounts.github_http.requests.post", post)
    monkeypatch.setattr("apps.accounts.github_http.requests.get", get)
    return emails, calls


def start(**overrides):
    return APIClient().post(START, {"redirect_uri": REDIRECT, "nonce": NONCE, **overrides},
                            format="json", HTTP_ORIGIN=ORIGIN)


def callback(started, **overrides):
    return APIClient().post(CALLBACK, {"code": "github-code", "state": started.data["state"],
                                      "nonce": NONCE, **overrides}, format="json", HTTP_ORIGIN=ORIGIN)


def account(*, password=None, superadmin=False):
    creator = User.objects.create_superuser if superadmin else User.objects.create_user
    return creator(username="github-member", email="primary@example.test",
                                    email_verified_at=timezone.now(), password=password,
                                    account_kind="platform" if superadmin else "member",
                                    is_superuser=superadmin, is_staff=superadmin,
                                    role="superadmin" if superadmin else "requester")


def link(user, provider="github", sub="1234567"):
    return SocialIdentity.objects.create(user=user, provider=provider, provider_sub=sub)


def form_data(row, **overrides):
    fields = ("google_web_client_id", "google_ios_client_id", "google_android_client_id",
              "apple_service_id", "apple_team_id", "apple_key_id", "github_client_id")
    return {**{field: getattr(row, field) for field in fields},
            "apple_native_app_ids": "[]", **overrides}


def test_new_user_pkce_member_session_and_secret_redaction(github, configured):
    started = start()
    assert started.status_code == 200, started.data
    assert "nonce" not in started.data
    query = parse_qs(urlsplit(started.data["authorization_url"]).query)
    attempt = OidcBrowserAttempt.objects.get()
    assert attempt.provider == "github" and NONCE not in attempt.nonce_digest
    assert query["scope"] == ["read:user user:email"]
    assert query["code_challenge_method"] == ["S256"]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(attempt.code_verifier.encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [challenge]
    result = callback(started)
    assert result.status_code == 200, result.data
    assert result.data["outcome"] == "created"
    assert "challenge" not in result.data
    user = SocialIdentity.objects.get(provider="github").user
    assert user.email == "primary@example.test" and user.email_verified_at
    assert not user.has_usable_password()
    access = AccessToken(result.data["access"])
    refresh = RefreshToken(result.cookies["refresh_token"].value)
    assert access["surface"] == refresh["surface"] == "member"
    assert access["mfa_source"] == refresh["mfa_source"] == "provider"
    configured.refresh_from_db()
    assert configured.github_client_secret.startswith("fernet:")
    assert configured.get_github_client_secret() == SECRET
    published = str((started.data, result.data, list(AuditLog.objects.values_list("meta", flat=True))))
    for value in (SECRET, TOKEN, NONCE, attempt.code_verifier, "github-code"):
        assert value not in published
    assert AuditLog.objects.filter(action="auth.social_login_succeeded", meta__provider="github").exists()


def test_gzip_encoded_github_responses_are_decoded(github, monkeypatch):
    plain_get = requests.get  # already the fixture's fake

    def gzipped_get(url, **kwargs):
        return JsonResponse(json.loads(plain_get(url, **kwargs).raw.read()), gzipped=True)

    monkeypatch.setattr("apps.accounts.github_http.requests.get", gzipped_get)
    result = callback(start())
    assert result.status_code == 200, result.data
    assert SocialIdentity.objects.get(provider="github").user.email == "primary@example.test"


def test_callback_adopts_pending_imported_memberships(github, monkeypatch):
    adopted = []
    monkeypatch.setattr("apps.accounts.views_github.adopt_pending_memberships_for_user",
                        lambda user: adopted.append(user.email) or [])
    assert callback(start()).status_code == 200
    assert adopted == ["primary@example.test"]


@pytest.mark.parametrize("linked", [False, True])
def test_existing_verified_account_linking_and_mfa_skip(github, linked):
    user = account(password="existing-password")
    enrolled(user)
    if linked:
        link(user)
    result = callback(start())
    assert result.status_code == 200, result.data
    assert result.data["outcome"] == ("existing" if linked else "auto_linked")
    assert "challenge" not in result.data
    assert AccessToken(result.data["access"])["mfa_source"] == "provider"
    assert SocialIdentity.objects.get(provider="github").user_id == user.pk
    assert User.objects.count() == 1


def test_unverified_local_email_is_not_auto_linked(github):
    user = account()
    user.email_verified_at = None
    user.save(update_fields=["email_verified_at"])
    result = callback(start())
    assert result.status_code == 409 and result.data["code"] == "account_link_required"
    assert not SocialIdentity.objects.exists()


@pytest.mark.parametrize("emails", [[],
    [{"email": "x@example.test", "primary": False, "verified": True}],
    [{"email": "x@example.test", "primary": True, "verified": False}],
    [{"email": "x@example.test", "primary": "true", "verified": "true"}],
    [{"email": "invalid", "primary": True, "verified": True}],
])
def test_requires_primary_literal_verified_email(github, emails):
    github[0][:] = emails
    result = callback(start())
    assert result.status_code == 401 and result.data["code"] == "social_invalid"
    assert not User.objects.exists()


@pytest.mark.parametrize("case", ["nonce", "unsolicited", "expired", "origin", "provider"])
def test_browser_binding_refused_before_any_http(github, case):
    started = start()
    attempt = OidcBrowserAttempt.objects.get()
    overrides = {}
    if case == "nonce":
        overrides["nonce"] = "wrong-browser"
    elif case == "unsolicited":
        overrides["state"] = "unsolicited"
    elif case == "expired":
        attempt.expires_at = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=["expires_at"])
    elif case == "origin":
        attempt.origin = "https://another.example.test"
        attempt.save(update_fields=["origin"])
    else:
        attempt.provider = "oidc:campus"
        attempt.save(update_fields=["provider"])
    result = callback(started, **overrides)
    assert result.status_code == 401 and not github[1]
    assert "refresh_token" not in result.cookies


def test_attempt_is_single_use(github):
    started = start()
    assert callback(started).status_code == 200
    count = len(github[1])
    assert callback(started).status_code == 401
    assert len(github[1]) == count


@pytest.mark.parametrize("switch", ["social", "members", "credentials", "provider"])
def test_start_and_callback_recheck_policy(github, monkeypatch, configured, switch):
    started = start()
    if switch == "social":
        PlatformLoginMethods.objects.create(pk=1, social_enabled=False)
    elif switch == "provider":
        PlatformLoginMethods.objects.create(pk=1, github_enabled=False)
    elif switch == "members":
        monkeypatch.setattr("apps.accounts.member_identity.member_accounts_enabled", lambda: False)
    else:
        configured.github_client_id = ""
        configured.save(update_fields=["github_client_id"])
    assert start(nonce="b" * 64).status_code == 503
    result = callback(started)
    assert result.status_code == 503 and result.data["code"] == "social_unavailable"
    assert not github[1]
    assert OidcBrowserAttempt.objects.get().consumed_at


def test_registration_switch_refuses_creation_but_allows_existing(github):
    PlatformLoginMethods.objects.create(pk=1, self_registration_enabled=False)
    response = callback(start())
    assert response.status_code == 403 and response.data["code"] == "registration_disabled"
    user = account()
    link(user)
    OidcBrowserAttempt.objects.all().delete()
    assert callback(start()).status_code == 200


@pytest.mark.parametrize("stage", ["exchange", "user", "emails"])
@pytest.mark.parametrize("failure", ["timeout", "bad_json", "status", "oversize"])
def test_external_failures_are_typed_503(github, monkeypatch, settings, stage, failure):
    started = start()
    method = "post" if stage == "exchange" else "get"
    original = getattr(requests, method)
    target = {"exchange": "https://github.com/login/oauth/access_token",
              "user": "https://api.github.com/user", "emails": "https://api.github.com/user/emails"}[stage]

    def fail(url, **kwargs):
        if url != target:
            return original(url, **kwargs)
        if failure == "timeout":
            raise requests.Timeout("provider unavailable")
        if failure == "bad_json":
            return JsonResponse({}, body=b"not-json")
        if failure == "status":
            return JsonResponse({}, status=503)
        return JsonResponse({}, headers={"Content-Length": str(settings.OIDC_HTTP_MAX_BYTES + 1)})

    monkeypatch.setattr(f"apps.accounts.github_http.requests.{method}", fail)
    result = callback(started)
    assert result.status_code == 503 and result.data["code"] == "social_unavailable"
    assert "refresh_token" not in result.cookies
    assert SECRET not in str(result.data) and TOKEN not in str(result.data)


def test_secret_never_rendered_by_api_or_admin(configured):
    admin = account(password="admin-password", superadmin=True)
    api = APIClient()
    api.force_authenticate(admin)
    response = api.get(SETTINGS)
    assert response.status_code == 200, response.data
    assert response.data["github_client_secret_set"] is True
    assert "github_client_secret" not in response.data
    control = Client()
    control.force_login(admin)
    page = control.get("/control/accounts/platformsocialauthsettings/1/change/")
    assert page.status_code == 200
    for value in (SECRET, configured.github_client_secret):
        assert value not in page.content.decode()
        assert value not in str(response.data)
    form = PlatformSocialAuthSettingsForm(instance=configured)
    assert "github_client_secret" not in form.fields
    assert form.fields["github_client_secret_raw"].widget.render_value is False


@pytest.mark.parametrize("change", [{"github_client_id": ""}, {"clear_github_client_secret": True}])
def test_github_only_lockout_form_and_api(configured, change):
    link(account())
    serializer = PlatformSocialAuthSettingsSerializer(instance=configured, data=change, partial=True)
    assert not serializer.is_valid() and "lock out" in str(serializer.errors)
    form = PlatformSocialAuthSettingsForm(data=form_data(configured, **change), instance=configured)
    assert not form.is_valid() and "lock out" in str(form.errors)


def test_blank_secret_keeps_value_and_explicit_clear_erases_it(configured):
    serializer = PlatformSocialAuthSettingsSerializer(instance=configured, data={"github_client_secret": ""}, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert serializer.save().get_github_client_secret() == SECRET
    form = PlatformSocialAuthSettingsForm(data=form_data(configured), instance=configured)
    assert form.is_valid(), form.errors
    assert form.save().get_github_client_secret() == SECRET
    form = PlatformSocialAuthSettingsForm(data=form_data(configured, clear_github_client_secret=True), instance=configured)
    assert form.is_valid(), form.errors
    assert not form.save().github_client_secret_set


def test_settings_patch_encrypts_and_audits_without_secret_values(configured):
    admin = account(password="admin-password", superadmin=True)
    client = APIClient()
    client.force_authenticate(admin)
    replacement = "replacement-github-secret"
    result = client.patch(SETTINGS, {"github_client_secret": replacement}, format="json")
    assert result.status_code == 200, result.data
    configured.refresh_from_db()
    assert configured.get_github_client_secret() == replacement
    assert configured.github_client_secret != replacement
    audit = AuditLog.objects.get(action="platform.social_auth_settings_updated")
    assert replacement not in str((result.data, audit.meta))
    assert configured.github_client_secret not in str((result.data, audit.meta))
    # A blank input keeps it, while an explicit clear removes it.
    assert client.patch(SETTINGS, {"github_client_secret": ""}, format="json").status_code == 200
    configured.refresh_from_db()
    assert configured.get_github_client_secret() == replacement
    assert client.patch(SETTINGS, {"clear_github_client_secret": True}, format="json").status_code == 200
    configured.refresh_from_db()
    assert not configured.github_client_secret_set


@pytest.mark.parametrize("change", [{"github_client_id": ""}, {"clear_github_client_secret": True}])
def test_settings_patch_refuses_github_only_lockout(configured, change):
    link(account())
    admin = User.objects.create_superuser(username="platform-admin", email="admin@example.test", password="password")
    client = APIClient()
    client.force_authenticate(admin)
    result = client.patch(SETTINGS, change, format="json")
    assert result.status_code == 400 and "lock out" in str(result.data)
    configured.refresh_from_db()
    assert configured.github_client_id and configured.get_github_client_secret() == SECRET


def test_member_login_switches_keep_platform_password_door_available():
    user = account(password="password", superadmin=True)
    link(user)
    form = PlatformLoginMethodsForm(data={"password_enabled": False, "social_enabled": True,
                                         "phone_enabled": True, "self_registration_enabled": True,
                                         "mfa_enabled": True})
    assert form.is_valid(), form.errors
    form.save()
    signed_in = APIClient().post("/api/v1/auth/login", {
        "username": user.username, "password": "password", "context": "platform",
    }, format="json", HTTP_ORIGIN=ORIGIN)
    assert signed_in.status_code == 200, signed_in.data


def test_platform_legacy_social_identities_do_not_block_member_provider_changes(configured):
    user = account(superadmin=True)
    link(user)
    link(user, "google", "google-subject")
    configured.google_web_client_id = "google-client"
    configured.save()
    with pytest.raises(SocialResolutionError) as error:
        unlink_social_identity(user, "google")
    assert error.value.code == "last_credential"
    form = PlatformSocialAuthSettingsForm(data=form_data(configured, google_web_client_id=""), instance=configured)
    assert form.is_valid(), form.errors
    configured.refresh_from_db()
    serializer = PlatformSocialAuthSettingsSerializer(instance=configured, data={"google_web_client_id": ""}, partial=True)
    assert serializer.is_valid(), serializer.errors
    # No member provider can authenticate a platform account.
    from apps.accounts.services_social_login import assert_social_user_active
    with pytest.raises(SocialResolutionError):
        assert_social_user_active(user)


def test_public_config_only_advertises_ready_member_github(configured, monkeypatch):
    assert APIClient().get("/api/v1/config").data["social_auth"]["github"] is True
    monkeypatch.setattr("apps.accounts.member_identity.member_accounts_enabled", lambda: False)
    assert "github" not in APIClient().get("/api/v1/config").data.get("social_auth", {})
    monkeypatch.setattr("apps.accounts.member_identity.member_accounts_enabled", lambda: True)
    configured.set_github_client_secret("")
    configured.save()
    assert "github" not in APIClient().get("/api/v1/config").data.get("social_auth", {})


def test_claim_credentials_refused_at_both_routes():
    for name in ("social-github-browser-start", "social-github-browser-callback"):
        assert isinstance(policy_for(name, "POST"), Refused)
