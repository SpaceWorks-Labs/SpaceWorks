"""Install-time choices, complete-state lockout protection and operator recovery."""
from io import StringIO

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.accounts.admin_social import PlatformLoginMethodsAdmin, PlatformLoginMethodsForm
from apps.accounts.login_methods import LOGIN_METHODS_CACHE_KEY, provider_login_enabled
from apps.accounts.login_methods_services import update_login_methods
from apps.accounts.login_methods_validation import validate_login_methods
from apps.accounts.models import PlatformLoginMethods, User
from apps.accounts.models_oidc import OidcProvider
from apps.accounts.models_social import PlatformSocialAuthSettings, SocialIdentity
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


@pytest.fixture
def credentials():
    row = PlatformSocialAuthSettings.load()
    row.google_web_client_id = "google-client"
    row.apple_service_id = "apple-client"
    row.github_client_id = "github-client"
    row.set_github_client_secret("private-client-secret")
    row.save()
    return row


def identity_user(*providers, superadmin=False, password=None):
    username = f"account-{User.objects.count()}"
    creator = User.objects.create_superuser if superadmin else User.objects.create_user
    user = creator(username=username, email=f"{username}@example.org", password=password)
    for provider in providers:
        SocialIdentity.objects.create(user=user, provider=provider, provider_sub=str(user.pk))
    return user


def proposed(**changes):
    return PlatformLoginMethods(**changes)


def test_simultaneous_removals_refused_by_form_and_command(credentials):
    identity_user("google", "apple")
    form = PlatformLoginMethodsForm(data={
        "password_enabled": True, "social_enabled": True,
        "google_enabled": False, "apple_enabled": False, "github_enabled": True,
    })
    assert not form.is_valid()
    assert "lock out" in str(form.errors)
    with pytest.raises(CommandError, match="lock out"):
        call_command("set_login_methods", "--providers", "github")
    assert not PlatformLoginMethods.objects.exists()  # Failed first write rolls back creation.


@pytest.mark.parametrize("changes", [
    {"social_enabled": False},
    {"google_enabled": False, "apple_enabled": False},
    {"password_enabled": False, "google_enabled": False, "apple_enabled": False},
])
def test_complete_state_protects_social_only_users(credentials, changes):
    identity_user("google", "apple")
    with pytest.raises(ValidationError, match="lock out"):
        validate_login_methods(proposed(**changes))


@pytest.mark.parametrize("provider,changes", [
    ("github", {}),
    ("google", {"google_enabled": False}),
    ("apple", {"apple_enabled": False}),
    ("oidc:missing", {}),
])
def test_member_provider_changes_do_not_control_platform_passwords(credentials, provider, changes):
    identity_user(provider, superadmin=True, password="existing-password")
    validate_login_methods(proposed(password_enabled=False, **changes))


def test_unconfigured_identity_is_not_a_rescue():
    identity_user("google", superadmin=True, password="existing-password")
    validate_login_methods(proposed(password_enabled=False))


def test_configured_oidc_survives_builtin_removals():
    identity_user("oidc:campus", superadmin=True)
    oidc = OidcProvider.objects.create(
        slug="campus", display_name="Campus", issuer="https://id.example.org",
        jwks_url="https://id.example.org/jwks", client_id="campus-client",
    )
    policy = proposed(password_enabled=False, google_enabled=False, apple_enabled=False, github_enabled=False)
    validate_login_methods(policy)
    oidc.is_enabled = False
    oidc.save()
    validate_login_methods(policy)


def test_usable_password_and_inactive_users_do_not_block_removal(credentials):
    identity_user("google", password="usable-password")
    inactive = identity_user("apple")
    inactive.is_active = False
    inactive.save()
    validate_login_methods(proposed(google_enabled=False, apple_enabled=False))


def test_enabled_configured_staff_provider_rescues_admin(credentials):
    identity_user("google", "github", superadmin=True)
    validate_login_methods(proposed(password_enabled=False, apple_enabled=False))


def test_unlink_cannot_count_disabled_password_or_disabled_provider(credentials):
    from apps.accounts.services_social_identity import SocialResolutionError, unlink_social_identity

    user = identity_user("google", "apple", password="stored-password")
    PlatformLoginMethods.objects.create(pk=1, password_enabled=False, apple_enabled=False)
    with pytest.raises(SocialResolutionError) as error:
        unlink_social_identity(user, "google")
    assert error.value.code == "last_credential"


@pytest.mark.parametrize("value", ["discord", "none,google", "google,", "Google"])
def test_command_invalid_providers_leave_no_row(value):
    with pytest.raises(CommandError):
        call_command("set_login_methods", "--providers", value, stdout=StringIO())
    assert not PlatformLoginMethods.objects.exists()


@pytest.mark.parametrize("value", ["", "none"])
def test_command_empty_selection_and_audit(value):
    call_command("set_login_methods", "--providers", value, "--mfa", "off", stdout=StringIO())
    row = PlatformLoginMethods.load()
    assert not any((row.google_enabled, row.apple_enabled, row.github_enabled, row.mfa_enabled))
    audit = AuditLog.objects.get(action="platform.login_methods_updated")
    assert audit.meta["source"] == "command"
    assert set(audit.meta["fields"]) == {"google_enabled", "apple_enabled", "github_enabled", "mfa_enabled"}


def test_command_reuses_stored_state_and_refuses_stranding_members(credentials):
    identity_user("google")
    PlatformLoginMethods.objects.create(pk=1, password_enabled=False)
    with pytest.raises(CommandError, match="lock out"):
        call_command("set_login_methods", "--providers", "github", "--mfa", "off")
    row = PlatformLoginMethods.load()
    assert row.google_enabled and row.mfa_enabled
    assert not AuditLog.objects.filter(action="platform.login_methods_updated").exists()


def test_setup_applies_only_on_first_creation(monkeypatch):
    monkeypatch.setenv("SETUP_MFA_ENABLED", "n")
    monkeypatch.setenv("SETUP_SOCIAL_PROVIDERS", "none")
    options = dict(username="install-owner", password="install-password", makerspace_name="Install Space")
    call_command("setup_instance", **options, stdout=StringIO())
    row = PlatformLoginMethods.load()
    assert not row.mfa_enabled and not row.google_enabled and not row.github_enabled
    update_login_methods({"mfa_enabled": True, "apple_enabled": True})
    call_command("setup_instance", **options, stdout=StringIO())
    row.refresh_from_db()
    assert row.mfa_enabled and row.apple_enabled and not row.google_enabled
    assert AuditLog.objects.filter(action="platform.login_methods_updated", meta__source="setup").count() == 1


def test_setup_uses_shared_stranding_guard(monkeypatch, credentials):
    identity_user("google")
    monkeypatch.setenv("SETUP_SOCIAL_PROVIDERS", "none")
    with pytest.raises(CommandError, match="lock out"):
        call_command("setup_instance", username="install-root", password="install-password", stdout=StringIO())
    assert not PlatformLoginMethods.objects.exists()


@pytest.mark.parametrize("key,value", [("SETUP_MFA_ENABLED", "maybe"), ("SETUP_SOCIAL_PROVIDERS", "unknown")])
def test_setup_rejects_invalid_install_choices(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(CommandError):
        call_command("setup_instance", username="bad-install", password="install-password", stdout=StringIO())
    assert not PlatformLoginMethods.objects.exists()


def test_setup_rerun_ignores_obsolete_environment(monkeypatch):
    PlatformLoginMethods.objects.create(pk=1, google_enabled=False)
    monkeypatch.setenv("SETUP_MFA_ENABLED", "obsolete")
    monkeypatch.setenv("SETUP_SOCIAL_PROVIDERS", "obsolete")
    call_command("setup_instance", username="existing-install", password="install-password", stdout=StringIO())
    assert not PlatformLoginMethods.load().google_enabled


def test_policy_write_rolls_back_if_audit_fails(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr("apps.accounts.login_methods_services.record_auth_event", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        update_login_methods({"mfa_enabled": False})
    assert not PlatformLoginMethods.objects.exists()


@pytest.mark.parametrize("provider", ["google", "apple", "github"])
def test_off_provider_hidden_and_endpoint_refused_with_keys(credentials, provider):
    client = APIClient()
    assert provider in client.get("/api/v1/config").data["social_auth"]
    PlatformLoginMethods.objects.create(pk=1, **{f"{provider}_enabled": False})
    assert provider not in client.get("/api/v1/config").data.get("social_auth", {})
    if provider == "github":
        from apps.accounts.github_browser import GithubUnavailable, github_settings
        with pytest.raises(GithubUnavailable):
            github_settings()  # Shared by both start and callback.
    else:
        response = client.post(f"/api/v1/auth/social/{provider}", {
            "id_token": "unused", "nonce": "unused", "surface": "member",
            "delivery": "web", "client_platform": "web",
        }, format="json")
        assert response.status_code == 404
        nonce = client.post("/api/v1/auth/social/nonce", {
            "provider": provider, "surface": "member", "delivery": "web", "client_platform": "web",
        }, format="json")
        assert nonce.status_code == 404


def test_last_known_good_cache_keeps_provider_off(monkeypatch):
    from django.core.cache import cache

    PlatformLoginMethods.objects.create(pk=1, google_enabled=False)
    assert not provider_login_enabled("google")
    monkeypatch.setattr(PlatformLoginMethods, "load", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    assert not provider_login_enabled("google")
    cache.delete(LOGIN_METHODS_CACHE_KEY)


def test_admin_readonly_fields_and_api_flags(credentials):
    from django.test import RequestFactory

    control = PlatformLoginMethodsAdmin(PlatformLoginMethods, admin.site)
    assert set(control.readonly_fields) == {"mfa_enabled", "google_enabled", "apple_enabled", "github_enabled",
                                            "sign_in_protection"}  # S-C status line
    root = identity_user(superadmin=True, password="root-password")
    PlatformLoginMethods.objects.create(pk=1, github_enabled=False)
    request = RequestFactory().get("/control/")
    request.user = root
    fields = control.get_form(request, obj=PlatformLoginMethods.load()).base_fields
    assert not set(control.readonly_fields) & set(fields)
    client = APIClient()
    client.force_authenticate(root)
    url = "/api/v1/admin/platform/social-auth-settings"
    assert client.get(url).data["github_enabled"] is False
    response = client.patch(url, {"github_enabled": True}, format="json")
    assert response.status_code == 200 and response.data["github_enabled"] is False
    assert PlatformLoginMethods.load().github_enabled is False
