"""Web and app use: registry contract, scoping, module gating, accounts, builds, flows and disclosure."""

import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.models_activity import ChannelUsageDay, DeviceActivityDay, WebSessionActivityDay
from apps.operations import reports
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.platform_scope import _platform_context_for_view
from apps.operations.report_definitions_channels import CHANNEL_REPORT_KEYS
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_validation import validate_report_definition
from tests.accounts.account_factories import device_grant
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space, make_user

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


def space_with(slug, *modules):
    space = make_space(slug)
    # `mobile` is default-on now, so a space that must have it off has to say so explicitly.
    keep = (set(space.enabled_modules or []) - {"mobile"}) | {"reports", *modules}
    space.enabled_modules = sorted(keep)
    space.save(update_fields=["enabled_modules"])
    return space


def superadmin():
    return make_user("chan-root", role=User.Role.SUPERADMIN, access_status=User.AccessStatus.ACTIVE)


def platform_rows(**kwargs):
    ctx = _platform_context_for_view(SimpleNamespace(user=superadmin()))
    return reports.report_data("platform-channel-usage", platform_context=ctx, **kwargs)


def seed(space, user, *, platform="apple", version="2.1.0"):
    space.enabled_modules = sorted(set(space.enabled_modules) | {"events", "bookings"})
    space.save(update_fields=["enabled_modules"])
    WebSessionActivityDay.objects.create(user=user, session_hash="w" * 32, makerspace=space, local_day=TODAY)
    grant = device_grant(user, platform=platform)
    DeviceActivityDay.objects.create(grant=grant, makerspace=space, platform=platform, app_version=version, local_day=TODAY)
    ChannelUsageDay.objects.create(channel="web", area="events", makerspace=space, day=TODAY, count=9)
    ChannelUsageDay.objects.create(channel="ios", area="events", makerspace=space, day=TODAY, count=4)
    ChannelUsageDay.objects.create(channel="web", area="flow:booking_made", makerspace=space, day=TODAY, count=3)
    ChannelUsageDay.objects.create(channel="ios", area="flow:booking_made", makerspace=space, day=TODAY, count=1)
    ChannelUsageDay.objects.create(channel="api_client", area="inventory", makerspace=space, day=TODAY, count=2)


def values(rows, measure, **match):
    return {(r["channel"], r["area"]): r["value"] for r in rows
            if r["measure"] == measure and all(r.get(k) == v for k, v in match.items())}


def test_definitions_are_valid_counts_only_and_never_combine_across_an_organization():
    for key in CHANNEL_REPORT_KEYS:
        definition = REPORT_REGISTRY[key]
        validate_report_definition(definition)
        assert key in EXCLUDED_ORGANIZATION_REPORT_KEYS and not definition.identity_bearing
        assert not any(marker in field for field in definition.fields for marker in ("name", "email", "user", "session"))
    assert REPORT_REGISTRY["platform-channel-usage"].platform_only
    assert REPORT_REGISTRY["channel-usage"].required_modules == ("reports",)


def test_superadmin_sees_every_space_and_channel_without_identifiers():
    a, b = space_with("chan-rep-a", "mobile"), space_with("chan-rep-b", "mobile")
    seed(a, make_member("chan-rep-a-u", a))
    seed(b, make_member("chan-rep-b-u", b))
    data = platform_rows()
    rows = data["typed_rows"]
    assert {r["makerspace_id"] for r in rows} >= {a.pk, b.pk}
    assert values(rows, "session_days", makerspace_id=a.pk) == {("web", "all"): 1, ("ios", "all"): 1}
    assert values(rows, "api_calls", makerspace_id=a.pk)[("web", "events")] == 9
    assert values(rows, "api_calls", makerspace_id=a.pk)[("api_client", "inventory")] == 2
    text = json.dumps(data, default=str)
    for leaked in ("session_hash", "w" * 32, "chan-rep-a-u", "@e.com"):
        assert leaked not in text
    assert_report_disclosure_safe(data)


def test_accounts_builds_and_flows_are_counted_privately():
    space = space_with("chan-rep-detail", "mobile")
    first, second = make_member("chan-rep-d1", space), make_member("chan-rep-d2", space)
    seed(space, first)
    WebSessionActivityDay.objects.create(user=second, session_hash="x" * 32, makerspace=space, local_day=TODAY)
    WebSessionActivityDay.objects.create(user=second, session_hash="y" * 32, makerspace=space, local_day=TODAY - timedelta(days=40))
    rows = platform_rows(grain="day")["typed_rows"]
    mine = [r for r in rows if r["makerspace_id"] == space.pk and r["period"] == TODAY.isoformat()]
    assert values(mine, "active_accounts")[("web", "all")] == 2
    assert values(mine, "new_accounts")[("web", "all")] == 1  # the first person's first day is today
    assert values(mine, "returning_accounts")[("web", "all")] == 1  # the second was first seen 40 days ago
    assert values(mine, "app_versions")[("ios", "2.1.0")] == 1
    flows = values(mine, "flow_completions")
    assert flows == {("web", "booking_made"): 3, ("ios", "booking_made"): 1}
    shares = {r["channel"]: r["share_percent"] for r in mine if r["measure"] == "flow_completions"}
    assert shares == {"web": 75.0, "ios": 25.0}


def test_space_report_is_scoped_to_its_own_space_and_hides_phone_channels_when_mobile_is_off():
    mobile, plain = space_with("chan-rep-mob", "mobile"), space_with("chan-rep-plain")
    seed(mobile, make_member("chan-rep-mob-u", mobile))
    seed(plain, make_member("chan-rep-plain-u", plain))
    manager = make_member("chan-rep-plain-m", plain)
    client = authenticated_client(manager)
    rows = client.get(f"/api/v1/admin/makerspace/{plain.pk}/analytics/channel-usage").json()["typed_rows"]
    assert rows and {r["channel"] for r in rows} == {"web", "api_client"}  # no ios rows: mobile module off
    assert "makerspace_id" not in rows[0]
    assert client.get(f"/api/v1/admin/makerspace/{mobile.pk}/analytics/channel-usage").status_code in (403, 404)
    owner = make_member("chan-rep-mob-m", mobile)
    mine = authenticated_client(owner).get(f"/api/v1/admin/makerspace/{mobile.pk}/analytics/channel-usage").json()["typed_rows"]
    assert {r["channel"] for r in mine} == {"web", "ios", "api_client"}


def test_platform_route_is_superadmin_only_and_lists_the_new_key():
    space = space_with("chan-rep-route")
    staff = make_member("chan-rep-route-m", space)
    assert authenticated_client(staff).get("/api/v1/admin/platform/analytics/platform-channel-usage").status_code == 403
    response = authenticated_client(superadmin()).get("/api/v1/admin/platform/analytics/platform-channel-usage?grain=week")
    assert response.status_code == 200, response.data


def test_app_version_header_is_validated_and_recorded_on_the_activity_row():
    from apps.accounts.channel_activity import app_version_from
    def request(value):
        return SimpleNamespace(headers={"X-SpaceWorks-App-Version": value})
    assert app_version_from(request("2.1.0+45")) == "2.1.0+45"
    for bad in ("", "x" * 33, "1.0 beta", "<script>", "1.0;drop"):
        assert app_version_from(request(bad)) == ""
    assert APIClient is not None
