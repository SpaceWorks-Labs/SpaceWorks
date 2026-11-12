import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.models_activity import AttestationVerificationLog, DeviceActivityDay
from apps.accounts.models_devices import NativeAppRegistration
from apps.backup.models import BackupRun
from apps.backup.models_runs import BackupRunCoverage
from apps.integrations.models import EmailLog, NotificationDeliveryLog
from apps.integrations.models_push import PushDevice
from apps.integrations.models_tracking import PushDeliveryAttempt, SmsSendLog
from apps.makerspaces.models import MakerspaceMembership
from apps.notifications.models_inbox import NotificationInboxRow
from apps.notifications.models_push import MemberPushDelivery
from apps.operations import reports
from apps.operations.platform_scope import _platform_context_for_view
from tests.accounts.account_factories import device_grant
from tests.operations.reconciliation_report_helpers import delivery
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.test_native_push import push_member
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db


def admin():
    return make_user("j-platform-admin", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)


def email(space, source, status="sent"):
    return EmailLog.objects.create(makerspace=space, provider_source=source, status=status,
                                    to_email="private@example.test", subject="secret", text_body="private")


def grant(user, fingerprint="a"):
    reg, _ = NativeAppRegistration.objects.get_or_create(makerspace=None, app_id="test.app", platform="android",
        environment="production", defaults={"verifier_config_key": "private", "status": "approved"})
    return device_grant(user, reg, attestation_subject_fingerprint=fingerprint * 64)


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_services_only_disclose_hidden_platform_daily_total_and_visible_own_counts(grain):
    # Decision 110: no hidden spaces exist any more (superadmin always on); a former
    # "hidden" space is an ordinary visible one, so its rows are reported per space.
    visible, hidden = make_space("j-visible"), make_space("j-hidden")
    actor = admin()
    make_member("j-hidden-local-staff", hidden)
    assert not MakerspaceMembership.objects.filter(user=actor).exists()
    email(visible, "platform")
    email(visible, "own", "failed")
    email(hidden, "platform")
    email(hidden, "platform", "failed")
    email(hidden, "own")
    SmsSendLog.objects.create(makerspace=hidden, purpose="authentication", provider_source="platform", status="failed")
    AttestationVerificationLog.objects.create(platform="android", mode="play", outcome="sent")
    ctx = _platform_context_for_view(SimpleNamespace(user=actor))
    data = reports.report_data("platform-services", platform_context=ctx, grain=grain)
    rows = data["typed_rows"]
    assert not any(r["bucket"] == "hidden_makerspaces" for r in rows)
    assert any(r["makerspace_id"] == visible.pk and r["provider_source"] == "own" and r["count"] == 1 for r in rows)
    assert_report_disclosure_safe(data)


def test_both_push_ledgers_count_device_outcomes_not_parent_delivery_or_retry_attempts():
    space = make_space("j-push")
    actor = admin()
    staff, member = make_member("j-push-staff", space), push_member("j-push-member", space)
    staff_push = PushDevice.objects.create(makerspace=space, user=staff, device_grant=grant(staff), provider="fcm",
        environment="production", token_ciphertext="private", token_fingerprint="b" * 64)
    member_push = PushDevice.objects.create(makerspace=space, user=member, device_grant=grant(member, "m"), provider="fcm",
        environment="production", token_ciphertext="private", token_fingerprint="m" * 64)
    log = NotificationDeliveryLog.objects.create(makerspace=space, channel="native_push", feature="members", event="created", status="sent", text_body="private")
    PushDeliveryAttempt.objects.create(delivery_log=log, push_device=staff_push, platform="android", status="sent", attempts=4)
    inbox = NotificationInboxRow.objects.create(makerspace=space, user=member, feature="members", event="created", event_key=uuid.uuid4(), title="private")
    parent = delivery(space, channel="native_push", state="failed", feature="members", audience="member")
    MemberPushDelivery.objects.create(envelope_delivery=parent, inbox_row=inbox, push_device=member_push, platform="android",
                                      provider_source="platform", status="failed", attempts=3)
    data = reports.report_data("platform-services", platform_context=_platform_context_for_view(SimpleNamespace(user=actor)))
    assert sum(r["count"] for r in data["typed_rows"] if r["service"] == "push") == 2
    assert_report_disclosure_safe(data)


@pytest.mark.parametrize("key", ["platform-services", "platform-usage"])
def test_platform_routes_refuse_normal_staff_and_tenant_org_export_schedule_paths(key):
    space = make_space("j-platform-route")
    staff = make_member("j-platform-staff", space)
    client = authenticated_client(staff)
    assert client.get(f"/api/v1/admin/platform/analytics/{key}").status_code == 403
    assert client.get("/api/v1/admin/platform/analytics/makerspaces").status_code == 403
    for path in (f"makerspace/{space.pk}/analytics/{key}", f"makerspace/{space.pk}/reports/{key}/export", f"organizations/123/analytics/{key}"):
        assert client.get(f"/api/v1/admin/{path}").status_code == 404
    response = client.post(f"/api/v1/admin/makerspaces/{space.pk}/report-schedules", {"report_key": key}, format="json")
    assert response.status_code in (400, 404)
    actor = admin()
    response = authenticated_client(actor).get(f"/api/v1/admin/platform/analytics/{key}?grain=week")
    assert response.status_code == 200, response.data
    assert_report_disclosure_safe(response.data)


def test_platform_picker_hard_blocks_hidden_tenants_and_is_paginated():
    visible, hidden = make_space("j-picker-visible"), make_space("j-picker-hidden")
    actor = admin()
    client = authenticated_client(actor)
    response = client.get("/api/v1/admin/platform/analytics/makerspaces")
    assert response.status_code == 200
    assert {r["id"] for r in response.data["results"]} >= {visible.pk, hidden.pk}
    # Platform principals have no local memberships; the separate tenant staff
    # account is the only local authority path into a hidden space.
    make_member("j-hidden-local-manager", hidden)
    response = client.get("/api/v1/admin/platform/analytics/makerspaces?report_key=machine-usage")
    assert {"count", "next", "previous", "results"} == set(response.data)


def test_usage_hides_business_growth_adoption_and_deduplicates_grants_across_spaces_and_null():
    a, b, hidden, archived = [make_space(f"j-usage-{name}") for name in ("a", "b", "hidden", "archived")]
    archived.archived_at = timezone.now()
    archived.save(update_fields=["archived_at"])
    for space in (a, b, hidden):
        space.enabled_modules = list(set(space.enabled_modules) | {"mobile", "member_accounts"})
        space.save(update_fields=["enabled_modules"])
    actor = admin()
    user = push_member("j-usage-user", a)
    device_grant = grant(user)
    for space in (a, b, None):
        DeviceActivityDay.objects.create(grant=device_grant, makerspace=space, local_day=timezone.localdate(), platform="android")
    hidden_user = push_member("j-hidden-session-user", hidden)
    hidden_grant = grant(hidden_user, "c")
    DeviceActivityDay.objects.create(grant=hidden_grant, makerspace=hidden, local_day=timezone.localdate(), platform="android")
    data = reports.report_data("platform-usage", platform_context=_platform_context_for_view(SimpleNamespace(user=actor)), limit=500)
    rows = data["typed_rows"]
    assert rows and all(r["makerspace_id"] != archived.pk for r in rows)
    sessions = [r for r in rows if r["metric"] == "active_app_sessions"]
    # Decision 110: no hidden-space bucket, so the "hidden" space is an ordinary visible one and its own
    # grant counts. The a/b/NULL rows of the first grant still dedupe to one session-day.
    assert sum(float(r["value"]) for r in sessions) == 2
    assert all("makerspace_id" in r for r in rows)
    assert_report_disclosure_safe(data)


def test_platform_window_and_invalid_grain_at_http_boundary():
    actor = admin()
    email(None, "platform")
    client = authenticated_client(actor)
    tomorrow = (timezone.now() + timedelta(days=1)).date().isoformat()
    response = client.get(f"/api/v1/admin/platform/analytics/platform-services?start={tomorrow}")
    assert response.status_code == 200 and not response.data["typed_rows"]
    assert client.get("/api/v1/admin/platform/analytics/platform-services?grain=quarter").status_code == 400


@pytest.mark.skip(reason="decision 110: hidden-makerspace bucket (superadmin off switch) removed; backup coverage is reported per space, covered by the live analytics suite")
def test_backup_run_coverage_is_counted_once_without_hidden_outcome_leakage():
    visible, hidden = make_space("j-backup-visible"), make_space("j-backup-hidden")
    actor = admin()
    run = BackupRun.objects.create(status="failed", cohort_at=timezone.now(), flag_snapshot={})
    BackupRunCoverage.objects.create(run=run, makerspace=visible, makerspace_id_snapshot=visible.pk, path="global", state="covered")
    BackupRunCoverage.objects.create(run=run, makerspace=hidden, makerspace_id_snapshot=hidden.pk, path="tenant", state="pending")
    data = reports.report_data("platform-services", platform_context=_platform_context_for_view(SimpleNamespace(user=actor)))
    backups = [r for r in data["typed_rows"] if r["service"] == "backups"]
    assert sum(r["count"] for r in backups) == 2
    assert len(backups) == 2
    hidden_row = next(r for r in backups if r["bucket"] == "hidden_makerspaces")
    assert hidden_row["status"] is None and hidden_row["makerspace_id"] is None
    assert_report_disclosure_safe(data)
