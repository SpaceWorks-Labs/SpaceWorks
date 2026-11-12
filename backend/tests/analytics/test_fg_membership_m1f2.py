"""Membership lifecycle and per-plan projections use scoped recorded history."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.makerspaces.module_install import install_module
from apps.operations.reports import report_data
from apps.operations.reports_membership_growth import build_membership_growth
from apps.operations.reports_membership_revenue import build_membership_revenue
from apps.operations.reports_retention import build_member_retention
from apps.operations.report_schedule_services import schedule_inputs
from apps.operations.views_report_helpers import date_range_from_dates
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.operations.test_membership_analytics import at, event, member, term
from tests.fixed_roles.helpers import staff_account
from tests.return_helpers import authenticated_client, make_space

pytestmark = pytest.mark.django_db


def space_fixture(slug):
    space = make_space(slug)
    install_module(space, "membership")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    return space


@pytest.mark.parametrize("grain,period", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_growth_local_buckets_and_reactivation_count_once(grain, period):
    space = space_fixture("fg-growth")
    membership = member(space, "fg-growth-person", at("2026-10-01"))
    joined, revoked, reactivated = (at(value) for value in (
        "2026-10-01", "2026-10-11T20:00:00", "2026-10-12T01:00:00"))
    event(space, membership, "membership.joined", joined)
    event(space, membership, "membership.revoked", revoked)
    event(space, membership, "membership.approved", reactivated)
    event(space, membership, "membership.approved", at("2026-10-12T02:00:00"))
    window = date_range_from_dates(date(2026, 10, 12), date(2026, 10, 12))
    result = build_membership_growth(space.pk, date_range=window, now=at("2026-10-13"), grain=grain)
    assert result.records == [dict(period=period, new_members=0, activated_members=1, revoked_members=1, active_members=1)]
    assert_report_disclosure_safe(result.records)


def test_growth_closing_balance_includes_activations_before_window_and_zero_periods():
    space = space_fixture("fg-growth-balance")
    member(space, "fg-growth-balance-person", at("2026-01-01"))
    window = date_range_from_dates(date(2026, 2, 2), date(2026, 2, 3))
    rows = build_membership_growth(space.pk, date_range=window, now=at("2026-03-01")).records
    assert len(rows) == 2
    assert all(row["active_members"] == 1 and row["activated_members"] == row["new_members"] == 0 for row in rows)


@pytest.mark.parametrize("grain,period", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_revenue_splits_plan_and_currency_and_normalizes_annual_price(grain, period):
    space = space_fixture("fg-plans")
    start, end = at("2026-01-01"), at("2027-01-01")
    monthly = member(space, "fg-plan-monthly", start)
    annual = member(space, "fg-plan-annual", start)
    foreign_currency = member(space, "fg-plan-euro", start)
    first = term(space, monthly, "Monthly", start, end, amount="30")
    second = term(space, annual, "Annual", start, end, amount="120", interval="yearly")
    term(space, foreign_currency, "Euro", start, end, amount="99", currency="eur")
    window = date_range_from_dates(date(2026, 10, 12), date(2026, 10, 12))
    rows = build_membership_revenue(space.pk, date_range=window, now=at("2026-10-13"), grain=grain).records
    assert {row["period"] for row in rows} == {period}
    by_plan = {row["plan_id"]: row for row in rows}
    assert by_plan[first.plan_id]["mrr"] == Decimal("30.00")
    assert by_plan[second.plan_id]["mrr"] == Decimal("10.00")
    assert by_plan[second.plan_id]["arr"] == Decimal("120.00")
    assert {row["currency"] for row in rows} == {"usd", "eur"}
    assert_report_disclosure_safe(rows)


def test_plan_switch_is_not_churn_and_overlapping_terms_count_once():
    space = space_fixture("fg-plan-switch")
    space.timezone = "UTC"
    space.save(update_fields=["timezone"])
    membership = member(space, "fg-plan-switch-person", at("2026-01-01"))
    term(space, membership, "Old", at("2026-01-01"), at("2026-02-02"), amount="20")
    selected = term(space, membership, "New", at("2026-02-01"), at("2027-01-01"), amount="40")
    rows = build_membership_revenue(space.pk, date_range=(at("2026-02-01"), at("2026-03-01")),
                                    now=at("2026-04-01")).records
    assert sum(row["recurring_members"] for row in rows) == 1
    assert sum(row["mrr"] for row in rows) == Decimal("40.00")
    assert next(row for row in rows if row["plan_id"] == selected.plan_id)["mrr"] == 40
    assert all(row["churned_members"] == row["reactivated_members"] == 0 for row in rows)


@pytest.mark.parametrize("key,builder", [
    ("membership-growth", build_membership_growth), ("member-retention", build_member_retention),
    ("membership-revenue", build_membership_revenue),
])
def test_membership_tenant_and_deployment_scopes_never_disclose_foreign_person(key, builder):
    own, other = space_fixture("fg-own"), space_fixture("fg-other")
    own_member = member(own, "fg-own-person", at("2025-01-01"))
    other_member = member(other, "fg-foreign-person", at("2025-01-01"))
    term(own, own_member, "OwnPlan", at("2025-01-01"), at("2028-01-01"))
    term(other, other_member, "ForeignPlan", at("2025-01-01"), at("2028-01-01"), amount="999")
    # One account per person: a plain member holds no report authority, so the reader is a Space Manager.
    actor = staff_account(own, "fg-own-reader", "space_manager")
    assert builder(other.pk, actor=actor).records == []
    payload = report_data(key, own.pk, actor=actor, grain="month")
    assert "ForeignPlan" not in str(payload) and "fg-foreign-person" not in str(payload)
    aggregate = builder(None, actor=actor).records
    assert aggregate and {row["makerspace_id"] for row in aggregate} == {own.pk}
    assert_report_disclosure_safe(payload)
    assert_report_disclosure_safe(aggregate)


def test_retention_mature_anniversaries_are_counts_only():
    space = space_fixture("fg-retention")
    member(space, "fg-retained", at("2025-01-01"))
    member(space, "fg-revoked", at("2025-01-01"), status="revoked", revoked_at=at("2025-02-01"))
    row = build_member_retention(space.pk, months=3, now=at("2025-05-01")).records[0]
    assert (row["eligible_members"], row["retained_members"], row["retention_percent"]) == (2, 1, Decimal(50))
    assert_report_disclosure_safe(row)


def test_calendar_filters_match_preview_download_and_schedule_without_double_conversion():
    space = space_fixture("fg-calendar-paths")
    # Both timestamps fall just after local midnight on February 1, before UTC midnight.
    membership = member(space, "fg-calendar-person", at("2026-01-31T19:00:00"))
    term(space, membership, "Boundary", at("2026-01-31T19:00:00"), at("2027-01-01"))
    reader = staff_account(space, "fg-calendar-reader", "space_manager")
    client = authenticated_client(reader)
    route = f"/api/v1/admin/makerspace/{space.pk}"
    for key in ("membership-growth", "member-retention", "membership-revenue"):
        query = "start=2026-02-01&end=2026-02-01"
        response = client.get(f"{route}/analytics/{key}?{query}")
        assert response.status_code == 200, response.data
        assert response.data["typed_rows"]
        assert_report_disclosure_safe(response.data)
        schedule = SimpleNamespace(report_key=key, makerspace=space,
                                   filters={"start": "2026-02-01", "end": "2026-02-01"})
        window, filters = schedule_inputs(schedule, at("2026-03-01"))
        payload = report_data(key, space.pk, date_range=window, report_filters=filters,
                              grain="month" if key == "membership-revenue" else "day", actor=reader)
        assert payload["typed_rows"] == response.data["typed_rows"]
        download = client.get(f"{route}/reports/{key}/export?format=csv&{query}")
        assert download.status_code == 200
        content = b"".join(download.streaming_content).decode("utf-8-sig")
        assert "2026-02" in content
        assert_report_disclosure_safe(content)
