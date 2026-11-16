from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import NativeAppRegistration, User
from apps.accounts.models_activity import AttestationVerificationLog, DeviceActivityDay
from apps.audit.services import record
from apps.integrations.models import PushDevice
from apps.operations.platform_scope import _platform_context_for_view
from apps.operations.reports_mobile_auth import build_mobile_auth
from apps.operations.reports_mobile_devices import build_mobile_devices
from apps.operations.reports_mobile_platform import (
    global_app_registrations, platform_active_app_sessions, platform_attestation_outcomes,
)
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import make_space, make_user
from tests.test_native_push import device_client, push_member

pytestmark = pytest.mark.django_db
AT = datetime(2026, 10, 11, 20, tzinfo=UTC)


def activity(grant, space, day):
    return DeviceActivityDay.objects.create(grant=grant, makerspace=space, platform=grant.platform, local_day=day)


@pytest.mark.parametrize("grain,expected", [
    ("day", [("2026-10-12", 1), ("2026-10-13", 1)]),
    ("week", [("2026-10-12", 2)]), ("month", [("2026-10-01", 2)]),
])
def test_activity_uses_daily_grants_and_only_recorded_tenant_selection(grain, expected):
    space, other = make_space("hi-activity"), make_space("hi-activity-other")
    user = push_member("hi-activity-user", space)
    _, grant = device_client(user, space)
    activity(grant, space, date(2026, 10, 12))
    activity(grant, space, date(2026, 10, 13))
    activity(grant, other, date(2026, 10, 14))
    activity(grant, None, date(2026, 10, 15))
    rows = build_mobile_devices(space.pk, grain=grain).records
    sessions = [r for r in rows if r["metric"] == "active_app_sessions_grants"]
    assert [(r["period"], r["count"]) for r in sessions] == expected
    assert not any(r["metric"] == "app_registrations" for r in rows)
    assert next(r for r in rows if r["metric"] == "grants")["count"] == 1
    assert_report_disclosure_safe(rows)
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    window = (datetime(2026, 10, 11, 18, 30, tzinfo=UTC), datetime(2026, 10, 12, 18, 30, tzinfo=UTC))
    filtered = build_mobile_devices(space.pk, date_range=window).records
    assert [(r["period"], r["count"]) for r in filtered if r["metric"] == "active_app_sessions_grants"] == [("2026-10-12", 1)]


def test_device_events_local_week_grants_and_global_registration_exclusion():
    space, other = make_space("hi-devices"), make_space("hi-devices-other")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    user = push_member("hi-devices-user", space)
    _, grant = device_client(user, space, platform="android")
    activity(grant, space, date(2026, 10, 12))
    device = PushDevice.objects.create(makerspace=space, user=user, device_grant=grant,
        provider="fcm", environment="development", token_ciphertext="private credential",
        token_fingerprint="f" * 64, active=False, invalidated_at=AT)
    PushDevice.objects.filter(pk=device.pk).update(created_at=AT)
    NativeAppRegistration.objects.create(makerspace=other, app_id="private app", platform="android", environment="production")
    rows = build_mobile_devices(space.pk, grain="week").records
    events = [r for r in rows if r["metric"] in ("push_registrations", "push_invalidations")]
    assert len(events) == 2
    assert all(r["period"] == "2026-10-12" and r["platform"] == "android" and r["count"] == 1 for r in events)
    grants = next(r for r in rows if r["metric"] == "grants")
    assert (grants["authority"], grants["environment"], grants["status"]) == ("member", "development", "active")
    assert_report_disclosure_safe(rows)


def test_mobile_auth_uses_recorded_scope_and_closed_reason_vocabulary():
    space, other = make_space("hi-auth"), make_space("hi-auth-other")
    for tenant, meta in [(space, {"reason": "attestation_rejected", "platform": "android", "environment": "production"}),
                         (other, {"reason": "provider_unavailable"}),
                         (None, {"reason": "provider_unavailable"}),
                         (space, {"reason": "smtp private secret", "platform": "private destination", "payload": {"secret": "hidden"}}),
                         (None, {"makerspace_id": space.pk, "reason": "invalid_credentials"})]:
        record(None, "auth.device_login_failed", makerspace=tenant, meta=meta)
    record(None, "auth.device_login_succeeded", makerspace=space, meta={"platform": "apple"})
    AttestationVerificationLog.objects.create(platform="android", mode="external", outcome="failed")
    rows = build_mobile_auth(space.pk).records
    assert sum(r["count"] for r in rows if r["metric"] == "device_logins") == 4
    assert sum(r["count"] for r in rows if r["metric"] == "attestation") == 1
    assert {r["reason"] for r in rows} == {"attestation_rejected", "unknown", "none", "authentication_rejected"}
    assert_report_disclosure_safe(rows)


@pytest.mark.parametrize("grain,period", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_auth_local_grains(monkeypatch, grain, period):
    space = make_space("hi-auth-grain")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    # Audit rows are immutable: freeze the writer's clock rather than UPDATE them.
    class Clock:
        @staticmethod
        def now(_zone):
            return AT
    monkeypatch.setattr("apps.audit.services.datetime", Clock)
    record(None, "auth.device_login_succeeded", makerspace=space, meta={"platform": "apple"})
    assert build_mobile_auth(space.pk, grain=grain).records[0]["period"] == period


def test_platform_sources_require_context_and_deduplicate_grants_across_scopes():
    for builder in (global_app_registrations, platform_attestation_outcomes, platform_active_app_sessions):
        with pytest.raises(PermissionDenied):
            builder()
    space, other = make_space("hi-platform"), make_space("hi-platform-other")
    user = push_member("hi-platform-user", space)
    _, grant = device_client(user, space)
    for tenant in (space, other, None):
        activity(grant, tenant, date(2026, 10, 12))
    actor = make_user("hi-super", role=User.Role.SUPERADMIN)
    ctx = _platform_context_for_view(SimpleNamespace(user=actor))
    assert platform_active_app_sessions(platform_context=ctx).records == [{"period": "2026-10-12", "count": 1}]
    global_rows = global_app_registrations(platform_context=ctx).records
    assert sum(r["count"] for r in global_rows) == 1
    AttestationVerificationLog.objects.create(platform="android", mode="in_process", outcome="failed")
    outcomes = platform_attestation_outcomes(platform_context=ctx).records
    assert outcomes[0]["mode"] == "in_process" and outcomes[0]["count"] == 1
    assert_report_disclosure_safe(outcomes)
    assert_report_disclosure_safe(global_rows)
