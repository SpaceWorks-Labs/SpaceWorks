"""PROD-DELTA: live source switches and authority on the new channel reports."""

import pytest
from django.utils import timezone

from apps.accounts.models_activity import ChannelUsageDay, DeviceActivityDay
from apps.operations.reports_channel_usage import build_channel_usage
from tests.accounts.account_factories import device_grant
from tests.operations.test_channel_usage_report import platform_rows, space_with
from tests.return_helpers import authenticated_client, make_member

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("area,module", [("events", "events"), ("bookings", "bookings"), ("presence", "presence"),
                                          ("card_designs", "membership"),
                                          ("flow:event_registered", "events"), ("flow:booking_made", "bookings")])
def test_channel_dimensions_disappear_and_return_with_their_source(area, module):
    space = space_with("prod-delta-channel-source", module)
    if area == "card_designs":
        space.enabled_modules = ["reports", "member_accounts", "membership"]
        space.save(update_fields=["enabled_modules"])
    ChannelUsageDay.objects.create(channel="web", area=area, makerspace=space, day=timezone.localdate(), count=3)
    assert build_channel_usage(space.pk).records
    space.enabled_modules = [key for key in space.enabled_modules if key != module]
    space.save(update_fields=["enabled_modules"])
    assert build_channel_usage(space.pk).records == []
    space.enabled_modules.append(module)
    space.save(update_fields=["enabled_modules"])
    assert build_channel_usage(space.pk).records[0]["value"] == 3


@pytest.mark.parametrize("area,feature", [("procurement", "inventory.tobuy"), ("warranty", "inventory.warranty"),
                                          ("maintenance", "inventory.maintenance"), ("id_programmes", "membership.id_programmes")])
def test_folded_channel_dimension_obeys_its_capability(area, feature):
    space = space_with("prod-delta-channel-folded", "membership", "member_accounts")
    space.enabled_features = ["loans.enabled", feature]
    space.save(update_fields=["enabled_features"])
    ChannelUsageDay.objects.create(channel="web", area=area, makerspace=space, day=timezone.localdate(), count=2)
    assert build_channel_usage(space.pk).records
    space.enabled_features = []
    space.save(update_fields=["enabled_features"])
    assert build_channel_usage(space.pk).records == []


def test_mobile_tombstone_hides_unattributed_phone_activity_and_keeps_web(monkeypatch):
    space = space_with("prod-delta-channel-mobile", "mobile")
    user = make_member("prod-delta-channel-mobile-user", space)
    grant = device_grant(user)
    DeviceActivityDay.objects.create(grant=grant, makerspace=None, platform="apple", local_day=timezone.localdate())
    for channel in ("ios", "web"):
        ChannelUsageDay.objects.create(channel=channel, area="accounts", makerspace=None, day=timezone.localdate(), count=1)
    from types import SimpleNamespace
    from apps.operations import reports, reports_channel_usage, reports_platform_usage
    from apps.operations.platform_scope import _platform_context_for_view
    from tests.operations.test_channel_usage_report import superadmin
    original = reports_channel_usage.module_available
    monkeypatch.setattr(reports_channel_usage, "module_available", lambda key: key != "mobile" and original(key))
    monkeypatch.setattr(reports_platform_usage, "module_available", reports_channel_usage.module_available)
    ctx = _platform_context_for_view(SimpleNamespace(user=superadmin()))
    rows = reports.report_data("platform-channel-usage", platform_context=ctx)["typed_rows"]
    assert {row["channel"] for row in rows} == {"web"}
    usage = reports.report_data("platform-usage", platform_context=ctx)["typed_rows"]
    assert not any(row["metric"] == "active_app_sessions" for row in usage)


@pytest.mark.parametrize("role", ["inventory_manager", "machine_manager", "handover", "member"])
def test_channel_report_refuses_other_areas_managers_and_members(role):
    space = space_with("prod-delta-channel-role")
    user = make_member("prod-delta-channel-role-user", space, membership_role=role, role="requester")
    assert authenticated_client(user).get(f"/api/v1/admin/makerspace/{space.pk}/analytics/channel-usage").status_code in (403, 404)


def test_reports_switch_refuses_channel_report_without_removing_stored_counts():
    space = space_with("prod-delta-channel-reports")
    user = make_member("prod-delta-channel-reports-user", space)
    row = ChannelUsageDay.objects.create(channel="web", area="accounts", makerspace=space, day=timezone.localdate(), count=1)
    client = authenticated_client(user)
    url = f"/api/v1/admin/makerspace/{space.pk}/analytics/channel-usage"
    assert client.get(url).status_code == 200
    space.enabled_modules.remove("reports")
    space.save(update_fields=["enabled_modules"])
    response = client.get(url)
    assert response.status_code == 404 and response.data["code"] == "module_disabled"
    assert ChannelUsageDay.objects.filter(pk=row.pk).exists()
    space.enabled_modules.append("reports")
    space.save(update_fields=["enabled_modules"])
    assert client.get(url).status_code == 200


def test_platform_drill_choices_keep_shared_sessions_spaces_and_hide_reports_off():
    from apps.accounts.models_activity import WebSessionActivityDay
    a, b, off = (space_with(f"prod-delta-drill-{slug}") for slug in ("a", "b", "off"))
    off.enabled_modules.remove("reports")
    off.save(update_fields=["enabled_modules"])
    user = make_member("prod-delta-drill-user", a)
    for space in (a, b):
        WebSessionActivityDay.objects.create(user=user, makerspace=space, session_hash="d" * 32, local_day=timezone.localdate())
    result = platform_rows()
    assert sum(row["value"] for row in result["typed_rows"] if row["measure"] == "session_days") == 1
    assert set(result["meta"]["space_ids"]) >= {a.pk, b.pk}
    assert off.pk not in result["meta"]["space_ids"]
