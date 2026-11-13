"""G19 + X34 + X33 membership insights: renewals, bridge identity, lists, funnel, the switch."""
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.makerspaces.membership_plan_services import create_term
from apps.makerspaces.membership_renewals import _expire
from apps.operations.reports_membership_l4_lists import (
    build_member_register, build_membership_breakdown, build_membership_expiry_calendar, build_membership_win_back,
)
from apps.operations.reports_membership_l4_terms import build_membership_bridge, build_membership_renewals
from apps.operations.reports_membership_summary import build_membership_monthly_summary
from tests.makerspaces.l4_helpers import features_off, features_on, member, plan, space_with_manager
from tests.return_helpers import authenticated_client

pytestmark = pytest.mark.django_db


def _history(slug):
    space, manager = space_with_manager(slug)
    monthly = plan(space)
    now = timezone.now()
    renewed = member(f"{slug}-a", space)
    first = create_term(manager, renewed, monthly, starts_at=now - timedelta(days=50))
    create_term(manager, renewed, monthly, starts_at=first.ends_at, renewed_from=first)
    _expire(first)
    lapsed = member(f"{slug}-b", space)
    old = create_term(manager, lapsed, monthly, starts_at=now - timedelta(days=50))
    _expire(old)
    return space, manager, now


def test_renewal_rate_counts_terms_followed_within_grace():
    space, _manager, now = _history("rep-renew")
    rows = build_membership_renewals(space.pk, date_range=(now - timedelta(days=60), now), grain="month").records
    assert sum(row["due"] for row in rows) == 2 and sum(row["renewed"] for row in rows) == 1
    assert sum(row["first_year_due"] for row in rows) == 2


def test_bridge_identity_holds_every_period():
    space, _manager, now = _history("rep-bridge")
    for row in build_membership_bridge(space.pk, date_range=(now - timedelta(days=90), now), grain="week").records:
        assert row["start"] + row["joined"] + row["came_back"] - row["lapsed"] - row["revoked"] == row["end"]


def test_lists_breakdown_calendar_and_win_back():
    space, _manager, now = _history("rep-lists")
    assert {row["standing"] for row in build_member_register(space.pk).records} == {"ending_soon", "lapsed"}
    dimensions = {row["dimension"] for row in build_membership_breakdown(space.pk).records}
    assert {"plan", "join_source", "tenure", "record_gaps"} <= dimensions
    assert len({row["week_start"] for row in build_membership_expiry_calendar(space.pk).records}) == 13
    assert [row["name"] for row in build_membership_win_back(space.pk).records] != []
    summary = {row["metric"]: row["value"] for row in build_membership_monthly_summary(space.pk).records}
    assert {"members_at_start", "members_at_end", "terms_due", "open_join_requests"} <= summary.keys()


def test_reports_need_their_switch_and_the_register_is_identity_bearing():
    space, manager, _now = _history("rep-switch")
    client = authenticated_client(manager)
    url = reverse("analytics-generic", args=[space.pk, "membership-bridge"])
    features_off(space)
    assert client.get(url).status_code in (400, 404)
    features_on(space, "insights")
    assert client.get(url).status_code == 200
    from apps.operations.report_registry import REPORT_REGISTRY
    assert REPORT_REGISTRY["member-register"].identity_bearing and not REPORT_REGISTRY["member-register"].schedulable
    assert REPORT_REGISTRY["membership-monthly-summary"].schedulable
