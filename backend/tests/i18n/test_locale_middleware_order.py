"""Pins the locale middleware placement (phase 8 i18n) against the release-2 stack."""
import ast
import importlib
import inspect

from django.conf import settings

RESET = "config.locale_context.LocaleContextResetMiddleware"
LOCALE = "django.middleware.locale.LocaleMiddleware"
EXPLICIT = "config.locale_context.ExplicitLocaleMiddleware"
# Above the reset boundary: the recovery gate (scoped early-response helper) and layers
# that never build a product response of their own.
ALLOWED_ABOVE_RESET = {
    "apps.backup.middleware.DeploymentRecoveryGateMiddleware",
    "apps.events.middleware.CalendarFeedLogRedactionMiddleware",
    "config.request_id.RequestIdMiddleware",
    "apps.operations.route_metrics.RouteMetricsMiddleware",
}


def test_settings_values():
    assert settings.LANGUAGE_CODE == "en"
    assert settings.USE_I18N is True
    assert settings.LANGUAGES == [("en", "English")]
    assert [str(p) for p in settings.LOCALE_PATHS] == [str(settings.BASE_DIR / "locale")]
    assert "x-spaceworks-locale" in settings.CORS_ALLOW_HEADERS


def test_exact_adjacency_and_order():
    mw = settings.MIDDLEWARE
    assert mw[0] == "apps.backup.middleware.DeploymentRecoveryGateMiddleware"
    assert mw.index("config.request_id.RequestIdMiddleware") == 2
    reset = mw.index(RESET)
    assert set(mw[:reset]) == ALLOWED_ABOVE_RESET
    for inner in (
        "config.control_plane_access.ControlPlaneReachMiddleware",
        "apps.tenant_migration.middleware.SourceMigrationGateMiddleware",
        "apps.makerspaces.middleware.TenantHostValidationMiddleware",
        "apps.accounts.ip_guard_middleware.LoginIPGuardMiddleware",
        "apps.accounts.platform_tenant_pii.PlatformTenantPiiMiddleware",
        "apps.tenant_rls.middleware.TenantRlsBoundaryMiddleware",
    ):
        assert mw.index(inner) > reset, inner
    session = mw.index("django.contrib.sessions.middleware.SessionMiddleware")
    assert mw[session + 1] == LOCALE
    assert mw[session + 2] == EXPLICIT
    assert mw.index(LOCALE) < mw.index("django.middleware.common.CommonMiddleware")
    assert mw[-1] == "apps.tenant_rls.middleware.TenantRlsBoundaryMiddleware"


def _returns_response_directly(path):
    module_name, class_name = path.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_name), class_name)
    tree = ast.parse(inspect.getsource(cls).lstrip())
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Call):
            name = getattr(node.value.func, "attr", getattr(node.value.func, "id", ""))
            if name.endswith("Response") and name != "finalize_response":
                return True
    return False


def test_no_direct_response_middleware_above_the_reset_without_the_helper():
    mw = settings.MIDDLEWARE
    for path in mw[: mw.index(RESET)]:
        assert not _returns_response_directly(path), path
    source = inspect.getsource(importlib.import_module("apps.backup.middleware"))
    assert "early_response_locale" in source
