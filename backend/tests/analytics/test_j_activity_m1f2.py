from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from tests.accounts.account_factories import make_membership  # presence needs a community membership
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts import rbac
from apps.audit.services import record
from apps.makerspaces.models import MakerspaceMembership
from apps.operations import reports
from apps.operations.report_output import project_report_output
from apps.operations.report_date_ranges import CalendarDateRange
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.reports_j_activity import build_presence_activity, build_presence_activity_hours
from apps.presence.models import PresenceSession
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import authenticated_client, make_member, make_space

pytestmark = pytest.mark.django_db


def presence(space, actor, start, minutes=60, ended=None):
    membership = (MakerspaceMembership.objects.filter(user=actor, makerspace=space).first()
                  or make_membership(actor, space))  # one community row per person and space
    return PresenceSession.objects.create(makerspace=space, member=actor, membership=membership,
                                          started_at=start, expires_at=start + timedelta(minutes=minutes), ended_at=ended)


@pytest.mark.parametrize("grain,expected", [("day", "2026-10-13"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_presence_grains_duration_unique_people_and_tenant_isolation(grain, expected):
    space, other = make_space("j-presence"), make_space("j-presence-other")
    actor, outsider = make_member("j-visitor", space), make_member("j-other-visitor", other)
    at = datetime(2026, 10, 13, 10, tzinfo=dt_timezone.utc)
    presence(space, actor, at)
    presence(space, actor, at + timedelta(hours=2), ended=at + timedelta(hours=2, minutes=30))
    presence(other, outsider, at)
    raw = build_presence_activity(space.pk, grain=grain)
    row = raw.records[0]
    assert row["period"] == expected and row["visits"] == 2
    assert row["unique_visitors"] == 1 and row["declared_presence_seconds"] == 5400
    payload = reports.report_data("presence-activity", space.pk, grain=grain)
    assert "person_id" not in payload["rows"][0]
    assert_report_disclosure_safe(payload)
    assert not any("_visitors" in r for r in project_report_output(REPORT_REGISTRY["presence-activity"], raw).records)


def test_hourly_declared_occupancy_splits_overlapping_hours_and_clips_window():
    space = make_space("j-hours")
    space.timezone = "UTC"
    space.save(update_fields=["timezone"])
    actor = make_member("j-hours-actor", space)
    at = timezone.now() - timedelta(days=2)
    at = at.replace(hour=10, minute=30, second=0, microsecond=0)
    presence(space, actor, at, minutes=120)
    rows = build_presence_activity_hours(space.pk, date_range=(at + timedelta(minutes=15), at + timedelta(minutes=90))).records
    assert sum(r["declared_presence_seconds"] for r in rows) == 4500
    assert {r["hour"] for r in rows} == {10, 11}
    assert_report_disclosure_safe(reports.report_data("presence-activity-hours", space.pk))
    ranking = reports.report_data("presence-top-visitors", space.pk, actor=actor)
    assert ranking["typed_rows"][0]["person_id"] == actor.pk
    assert_report_disclosure_safe(ranking)


def test_presence_rankings_require_both_domain_action_and_audit(monkeypatch):
    space = make_space("j-ranking")
    actor = make_member("j-ranking-actor", space)
    original = rbac.can
    monkeypatch.setattr(rbac, "can", lambda user, action, ms: False if action == rbac.Action.VIEW_AUDIT else original(user, action, ms))
    with pytest.raises(PermissionDenied):
        reports.report_data("presence-top-visitors", space.pk, actor=actor)
    response = authenticated_client(actor).get(f"/api/v1/admin/makerspace/{space.pk}/reports/catalog")
    assert response.status_code == 200
    assert "presence-top-visitors" not in {r["key"] for r in response.data["results"]}


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_audit_counts_and_rankings_never_read_metadata_or_other_tenants(grain):
    space, other = make_space("j-audit"), make_space("j-audit-other")
    actor, outsider = make_member("j-audit-actor", space), make_member("j-audit-other-actor", other)
    record(actor, "user.password_changed", makerspace=space, meta={"token": "secret"})
    record(outsider, "user.password_changed", makerspace=other)
    data = reports.report_data("audit-activity", space.pk, grain=grain)
    assert sum(r["count"] for r in data["typed_rows"]) == 1
    assert data["typed_rows"][0]["action"] == "user.credential_changed"
    assert_report_disclosure_safe(data)
    ranked = reports.report_data("audit-top-actors", space.pk, actor=actor)
    assert ranked["typed_rows"] == [{"person_id": actor.pk, "count": 1, "declared_presence_seconds": None}]
    assert_report_disclosure_safe(ranked)
    assert_report_disclosure_safe(reports.report_data("audit-activity-hours", space.pk))
    denied = authenticated_client(outsider).get(f"/api/v1/admin/makerspace/{space.pk}/analytics/audit-activity")
    assert denied.status_code == 404


def test_presence_deployment_rows_always_keep_makerspace_id():
    space = make_space("j-presence-aggregate")
    actor = make_member("j-presence-aggregate-actor", space)
    presence(space, actor, timezone.now() - timedelta(hours=2))
    data = reports.report_data("presence-activity")
    assert all(r["makerspace_id"] == space.pk for r in data["typed_rows"])
    assert_report_disclosure_safe(data)


def test_presence_calendar_dates_are_rebound_to_the_tenant_for_all_builder_callers():
    space = make_space("j-presence-calendar")
    space.timezone = "America/Los_Angeles"
    space.save(update_fields=["timezone"])
    actor = make_member("j-calendar-actor", space)
    # Oct 13 UTC can still be Oct 12 locally. Only the second session belongs
    # to the requested Oct 13 local day; previews/exports/schedules share this.
    presence(space, actor, datetime(2026, 10, 13, 1, tzinfo=dt_timezone.utc))
    presence(space, actor, datetime(2026, 10, 14, 1, tzinfo=dt_timezone.utc))
    window = CalendarDateRange((datetime(2026, 10, 13, tzinfo=dt_timezone.utc), datetime(2026, 10, 14, tzinfo=dt_timezone.utc)))
    data = reports.report_data("presence-activity", space.pk, date_range=window)
    assert len(data["typed_rows"]) == 1
    assert data["typed_rows"][0]["period"] == "2026-10-13"
    assert data["typed_rows"][0]["visits"] == 1
