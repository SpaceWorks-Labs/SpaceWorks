"""#234: one self-hosted mode. The console switch, per-space limit overrides, guest-pass cap and throttle overrides."""

import pytest
from django.core.cache import cache
from rest_framework.exceptions import ValidationError
from rest_framework.throttling import UserRateThrottle

from apps.audit.models import AuditLog
from apps.makerspaces import limits
from apps.managed_hosting import throttle_rates
from apps.managed_hosting.availability import hosting_enabled, plans_enabled
from apps.managed_hosting.limits_console import effective_limits
from apps.managed_hosting.models import PlatformHostingBillingSettings, PlatformThrottleRate

from .helpers import api, space, superadmin

pytestmark = pytest.mark.django_db
PLATFORM = "/api/v1/admin/platform"


@pytest.fixture
def plain(settings):
    """A plain self-hosted install: no platform domain, no env override."""
    settings.PLATFORM_DOMAIN_SUFFIX = ""
    settings.MANAGED_PLANS_ENABLED = None
    cache.clear()
    return settings


def test_switch_defaults_off_and_hides_the_features(plain):
    lab = space()
    assert not hosting_enabled() and not plans_enabled()
    assert limits.resource_limit(lab, "members") is None
    assert api(superadmin()).get(PLATFORM + "/hosting-plans").status_code == 404
    assert "managed_plans" not in api().get("/api/v1/config").json()


def test_switch_on_enables_plans_and_audits(plain):
    root = superadmin()
    response = api(root).put(PLATFORM + "/hosting-switch", {"enabled": True}, format="json")
    assert response.status_code == 200 and response.json()["enabled"] is True
    assert plans_enabled()
    assert api(root).get(PLATFORM + "/hosting-plans").status_code == 200
    assert AuditLog.objects.filter(action="managed_hosting.hosting_switch_changed").exists()
    api(root).put(PLATFORM + "/hosting-switch", {"enabled": False}, format="json")
    assert not plans_enabled()
    assert PlatformHostingBillingSettings.load().pk == 1  # data kept


def test_env_override_forces_the_switch(plain):
    root = superadmin()
    PlatformHostingBillingSettings.objects.update_or_create(pk=1, defaults={"hosting_enabled": False})
    plain.MANAGED_PLANS_ENABLED = True
    assert hosting_enabled()
    assert api(root).put(PLATFORM + "/hosting-switch", {"enabled": False}, format="json").status_code == 400
    plain.MANAGED_PLANS_ENABLED = False
    PlatformHostingBillingSettings.objects.filter(pk=1).update(hosting_enabled=True)
    assert not hosting_enabled()


def test_space_override_beats_plan_and_default_and_is_audited(plain):
    plain.MANAGED_PLANS_ENABLED = True
    lab, root = space(), superadmin()
    assert limits.resource_limit(lab, "members") is None  # no plan, no platform domain: unlimited
    response = api(root).put(f"{PLATFORM}/spaces/{lab.pk}/limits", {"overrides": {"members": 3}}, format="json")
    assert response.status_code == 200
    row = next(r for r in response.json()["rows"] if r["key"] == "members")
    assert row["effective"] == 3 and row["source"] == "override" and row["used"] == 0
    assert AuditLog.objects.filter(action="space_control.limits_changed", makerspace=lab).exists()
    bad = api(root).put(f"{PLATFORM}/spaces/{lab.pk}/limits", {"overrides": {"nonsense": 1}}, format="json")
    assert bad.status_code == 400
    assert {r["key"] for r in effective_limits(lab)} >= {"members", "storage", "guest_passes"}


def test_guest_pass_cap_refuses_at_the_limit(plain):
    from apps.makerspaces.limits_usage import check_quota

    plain.MANAGED_PLANS_ENABLED = True
    lab = space(resource_limit_overrides={"guest_passes": 0})
    with pytest.raises(ValidationError):
        check_quota(lab, "guest_passes", adding=1)


def test_throttle_override_applies_and_default_returns(plain):
    scope = "login"
    default = throttle_rates.defaults()[scope]
    UserRateThrottle.scope = scope
    assert UserRateThrottle().get_rate() == default
    PlatformThrottleRate.objects.create(scope=scope, rate="20/min")
    assert UserRateThrottle().get_rate() == "20/min"  # save cleared the cache
    PlatformThrottleRate.objects.get(scope=scope).delete()
    assert UserRateThrottle().get_rate() == default


def test_throttle_bounds_and_audit_through_the_api(plain):
    root = superadmin()
    url = f"{PLATFORM}/request-limits/login"
    assert api(root).put(url, {"rate": "1/day"}, format="json").status_code == 400       # far too strict
    assert api(root).put(url, {"rate": "99999/sec"}, format="json").status_code == 400   # far too loose
    assert api(root).put(url, {"rate": "banana"}, format="json").status_code == 400
    assert api(root).put(f"{PLATFORM}/request-limits/not-a-scope", {"rate": "5/min"}, format="json").status_code == 404
    ok = api(root).put(url, {"rate": "20/min"}, format="json")
    assert ok.status_code == 200 and ok.json()["overridden"] is True and ok.json()["env_key"] == "THROTTLE_LOGIN"
    assert AuditLog.objects.filter(action="managed_hosting.throttle_rate_changed").count() == 1
    reset = api(root).delete(url)
    assert reset.json()["overridden"] is False and reset.json()["rate"] == reset.json()["default"]


def test_non_superadmin_cannot_change_rates_or_switch(plain):
    assert api().put(PLATFORM + "/hosting-switch", {"enabled": True}, format="json").status_code in (401, 403)
    assert api().put(PLATFORM + "/request-limits/login", {"rate": "20/min"}, format="json").status_code in (401, 403)
