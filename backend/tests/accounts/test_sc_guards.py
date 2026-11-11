"""S-C guards: migrations, system checks, middleware order, schema hook, catalogue, retention."""

from datetime import timedelta
from io import StringIO

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_no_pending_migrations():
    from apps.makerspaces.models import Makerspace, default_enabled_features, default_enabled_modules

    modules = Makerspace._meta.get_field("enabled_modules")
    features = Makerspace._meta.get_field("enabled_features")
    saved = modules.default, features.default
    modules.default, features.default = default_enabled_modules, default_enabled_features
    out = StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", verbosity=1, stdout=out)
    except SystemExit:
        pytest.fail(out.getvalue())
    finally:
        modules.default, features.default = saved


def test_accounts_system_checks_pass_and_the_proxy_warning_fires(settings):
    from django.core.checks import run_checks

    from apps.accounts.checks import check_proxy_topology
    problems = [item for item in run_checks(tags=["urls", "security", "database", "models"])
                if item.id.startswith("accounts.")]
    assert problems == []
    settings.BEHIND_TRUSTED_PROXY, settings.TRUSTED_PROXY_COUNT = True, 0
    assert [item.id for item in check_proxy_topology()] == ["accounts.W002"]
    settings.TRUSTED_PROXY_COUNT = 1
    assert check_proxy_topology() == []


def test_the_guard_runs_before_axes_and_the_validator_last():
    middleware = settings.MIDDLEWARE
    guard = middleware.index("apps.accounts.ip_guard_middleware.LoginIPGuardMiddleware")
    assert guard < middleware.index("axes.middleware.AxesMiddleware")
    assert guard > middleware.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    assert settings.AUTH_PASSWORD_VALIDATORS[-1]["NAME"] == "apps.accounts.password_breach.BreachedPasswordValidator"
    assert settings.AXES_WHITELIST_CALLABLE == "apps.accounts.ip_rules.axes_whitelisted"


def test_every_sign_in_family_view_is_flagged():
    from django.urls import resolve

    from apps.accounts.ip_guard_middleware import guarded
    for path in ("/api/v1/auth/login", "/api/v1/auth/member-sign-up", "/api/v1/auth/forgot-password",
                 "/api/v1/auth/reset-password", "/api/v1/auth/phone/login/start", "/api/v1/auth/phone/login/confirm",
                 "/api/v1/auth/social/google", "/api/v1/auth/social/apple", "/api/v1/auth/social/nonce",
                 "/api/v1/auth/social/github/authorize", "/api/v1/auth/social/github/callback",
                 "/api/v1/auth/social/oidc/callback", "/api/v1/auth/mfa/verify", "/api/v1/auth/mfa/enroll",
                 "/api/v1/auth/device/login", "/api/v1/auth/account-merge/start",
                 "/api/v1/auth/passkeys/authenticate/options", "/api/v1/auth/passkeys/authenticate/verify",
                 "/api/v1/auth/staff-invitations/accept", "/api/v1/auth/email-verification/resend"):
        match = resolve(path)
        assert guarded(match.func, match.view_name), path
    assert not guarded(resolve("/api/v1/auth/me").func, "auth-me")


def test_the_schema_documents_the_new_errors():
    from drf_spectacular.generators import SchemaGenerator

    schema = SchemaGenerator().get_schema(request=None, public=True)
    login = schema["paths"]["/api/v1/auth/login"]["post"]["responses"]
    assert "ip_blocked" in login["429"]["description"] and "captcha_required" in login["400"]["description"]
    device = schema["paths"]["/api/v1/auth/device/login"]["post"]["responses"]
    assert "ip_blocked" in device["429"]["description"] and "captcha" not in device.get("400", {}).get(
        "description", "")
    change = schema["paths"]["/api/v1/auth/change-password"]["post"]["responses"]
    assert "password_breached" in change["400"]["description"]
    assert "LoginGuardError" in schema["components"]["schemas"]
    assert "turnstile_site_key" in schema["components"]["schemas"]["PublicConfig"]["properties"]


def test_presentation_catalogue_lists_the_new_actions():
    from apps.audit.presentation_catalog import PRESENTATION_CATALOG
    from apps.audit.presentation_guards import presentation_catalog_errors

    assert {"auth.ip_auto_blocked", "auth.ip_unblocked", "auth.captcha_failed", "auth.password_breach_rejected",
            "platform.ip_rule_saved", "platform.ip_rule_deleted"} <= set(PRESENTATION_CATALOG)
    assert presentation_catalog_errors() == []


def test_retention_task_is_scheduled_catalogued_and_gate_exempt():
    from apps.operations.cloud_jobs.catalog import all_declarations
    from apps.tenant_migration import gate_policy

    path = "apps.accounts.tasks_login_security.purge_login_security_task"
    assert settings.CELERY_BEAT_SCHEDULE["purge-login-security"]["task"] == path
    assert path in {task.path for task in all_declarations()}
    assert path in gate_policy.TASK_EXEMPTIONS


def test_retention_deletes_blocks_seven_days_after_they_end_and_old_axes_rows():
    from axes.models import AccessAttempt

    from apps.accounts.models import IPAutoBlock
    from apps.accounts.tasks_login_security import purge_login_security_telemetry
    now = timezone.now()
    IPAutoBlock.objects.create(ip_key="a" * 64, network="203.0.113.1/32", blocked_until=now - timedelta(days=8))
    IPAutoBlock.objects.create(ip_key="b" * 64, network="203.0.113.2/32", blocked_until=now - timedelta(days=6))
    old = AccessAttempt.objects.create(username="x", ip_address="203.0.113.1", user_agent="", path_info="/",
                                       get_data="", post_data="", http_accept="", failures_since_start=1)
    AccessAttempt.objects.filter(pk=old.pk).update(attempt_time=now - timedelta(days=31))
    AccessAttempt.objects.create(username="y", ip_address="203.0.113.1", user_agent="", path_info="/",
                                 get_data="", post_data="", http_accept="", failures_since_start=1)
    result = purge_login_security_telemetry()
    assert list(IPAutoBlock.objects.values_list("network", flat=True)) == ["203.0.113.2/32"]
    assert list(AccessAttempt.objects.values_list("username", flat=True)) == ["y"]
    assert result["accounts.IPAutoBlock"] == 1
