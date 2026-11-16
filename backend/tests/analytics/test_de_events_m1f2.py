from datetime import timedelta
from decimal import Decimal

import pytest

from apps.events.models import EventFeedbackResponse, EventRegistration
from apps.operations import reports
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.reports_event_quality import numeric_scores
from tests.operations.report_assertions import assert_report_disclosure_safe
from .de_helpers_m1f2 import AT, BOUNDS, setup, event, registration, checkin, feedback, payment

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("grain,expected", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
@pytest.mark.parametrize("key", ("event-signups", "event-funnel", "event-checkin-times", "event-revenue", "event-feedback-scores"))
def test_event_grains(key, grain, expected):
    from apps.operations.reports_de_common import period_at
    space, actor = setup(f"de-event-grain-{key}-{grain}")
    workshop = event(space)
    reg = registration(workshop, actor, status="attended")
    arrival = checkin(reg)
    review = feedback(workshop)
    charge = payment(reg, actor)
    rows = reports.report_data(key, space.pk, grain=grain)["typed_rows"]
    source_at = charge.created_at if key == "event-revenue" else review.created_at if key == "event-feedback-scores" else arrival.attended_at
    expected_period = period_at(source_at, grain, space)
    assert rows and {r["period"] for r in rows} == {expected_period}
    assert_report_disclosure_safe(rows)


def test_cumulative_signups_include_baseline_and_idle_days_without_person_fields():
    space, actor = setup("de-signup-baseline")
    workshop = event(space)
    first = registration(workshop, actor, at=AT - timedelta(days=10))
    EventRegistration.objects.create(event=workshop, name="Other private", email="second@example.com", phone="1")
    EventRegistration.objects.filter(event=workshop).exclude(pk=first.pk).update(created_at=AT)
    rows = reports.report_data("event-signups", space.pk, date_range=BOUNDS)["typed_rows"]
    assert [(r["registrations"], r["cumulative_registrations"]) for r in rows] == [(1, 2), (0, 2)]
    assert_report_disclosure_safe(rows)


def test_checkin_uses_earliest_attendance_time_and_deduplicates_reentry():
    space, actor = setup("de-first-arrival")
    reg = registration(event(space), actor, status="attended")
    checkin(reg, AT + timedelta(minutes=30))
    checkin(reg, AT - timedelta(minutes=5))  # offline arrival recorded later
    checkin(reg, AT + timedelta(hours=1))
    rows = reports.report_data("event-checkin-times", space.pk, date_range=BOUNDS)["typed_rows"]
    assert len(rows) == 1 and rows[0]["checkin_count"] == 1
    assert rows[0]["timing_bucket"] == "Under 15 minutes early"
    # Deduplication precedes range filtering; reentry in a later window is not a new arrival.
    assert reports.report_data("event-checkin-times", space.pk, date_range=(AT, BOUNDS[1]))["typed_rows"] == []


def test_numeric_feedback_omits_private_answers_and_keeps_question_bases():
    import json
    space, actor = setup("de-score-summary")
    workshop = event(space)
    response = feedback(workshop, "5")
    EventFeedbackResponse.objects.create(survey=response.survey, answers_snapshot=json.dumps({"answers": [
        {"id": "score", "type": "number", "value": "1"},
        {"id": "hours", "type": "number", "value": "100"},
        {"id": "private", "type": "paragraph", "value": "private narrative"},
    ]}))
    rows = reports.report_data("event-feedback-scores", space.pk)["typed_rows"]
    scores = {r["question_id"]: r for r in rows}
    assert scores["score"]["average_score"] == "3.00"
    assert scores["score"]["score_count"] == 2
    assert scores["hours"]["average_score"] == "100.00"
    assert "private" not in scores
    assert_report_disclosure_safe(rows)
    assert list(numeric_scores('{"answers":[{"id":"x","type":"number","value":"NaN"}]}')) == []


def test_event_revenue_currency_and_discounts_use_host_ledger_even_without_rail():
    space, actor = setup("de-revenue")
    workshop = event(space)
    first = registration(workshop, actor, discount="3.00")
    payment(first, actor, "usd", "12.00")
    other = EventRegistration.objects.create(event=workshop, name="Private", email="money@example.com", phone="1", discount_amount="5.00")
    payment(other, actor, "eur", "20.00")
    # An otherwise similar registration without a ledger row supplies no frozen currency.
    EventRegistration.objects.create(event=workshop, name="Free", email="free@example.com", phone="1", discount_amount="999.00")
    space.enabled_modules = [m for m in space.enabled_modules if m != "payments"]
    space.save(update_fields=["enabled_modules"])
    rows = reports.report_data("event-revenue", space.pk)["typed_rows"]
    by_currency = {r["currency"]: r for r in rows}
    assert by_currency["usd"]["charged_amount"] == "12.00"
    assert by_currency["usd"]["promo_discount_amount"] == "3.00"
    assert by_currency["eur"]["promo_discount_amount"] == "5.00"
    assert sum(r["charge_count"] for r in rows) == 2
    assert_report_disclosure_safe(rows)


def test_organization_funnel_sums_denominators_not_percentages():
    rows = aggregate_rows("event-funnel", [(1, [dict(period="2026-10-12", registrations=1, confirmed=1, attended=1)]),
                                           (2, [dict(period="2026-10-12", registrations=9, confirmed=9, attended=0)])], limit=10)
    assert rows[0]["attendance_rate_percent"] == 10.0
    assert rows[0]["confirmation_rate_percent"] == 100.0


def test_revenue_counts_correction_heads_and_successful_refunds_once():
    from django.utils import timezone
    from apps.payments.models import Refund
    from apps.payments.reconciliation import mark_offline, amend_settlement
    space, actor = setup("de-revenue-corrections")
    reg = registration(event(space), actor, discount="2.50")
    charge = payment(reg, actor, amount="10.00")
    at = timezone.now()
    details = {"method": "cash", "reference": "receipt-A", "received_at": at}
    mark_offline(charge, actor, settlement=details)
    amend_settlement(actor=actor, makerspace_id=space.pk, payment_id=charge.pk,
                     settlement={**details, "method": "upi", "reference": "receipt-B"})
    original = Refund.objects.create(payment=charge, amount=Decimal("3.00"), currency="usd", provider="manual",
                                    status="succeeded", method="cash", refunded_at=at, settled_at=at, created_by=actor)
    Refund.objects.create(payment=charge, amount=Decimal("3.00"), currency="usd", provider="manual",
                          status="succeeded", method="upi", refunded_at=at, settled_at=at, created_by=actor, amends=original)
    Refund.objects.create(payment=charge, amount=Decimal("1.00"), currency="usd", provider="stripe",
                          status="failed", created_by=actor)
    rows = reports.report_data("event-revenue", space.pk)["typed_rows"]
    assert sum(Decimal(r["collected_amount"]) for r in rows) == Decimal("10.00")
    assert sum(Decimal(r["refunded_amount"]) for r in rows) == Decimal("3.00")
    assert sum(Decimal(r["promo_discount_amount"]) for r in rows) == Decimal("2.50")
    assert sum(Decimal(r["net_amount"]) for r in rows) == Decimal("7.00")
    assert_report_disclosure_safe(rows)


def test_organization_signup_curve_carries_idle_space_baselines():
    rows = aggregate_rows("event-signups", [
        (1, [dict(event_id=1, period="2026-10-12", registrations=1, cumulative_registrations=1)]),
        (2, [dict(event_id=2, period="2026-10-13", registrations=3, cumulative_registrations=3)]),
    ], limit=10)
    assert [r["cumulative_registrations"] for r in rows] == [1, 4]


def test_organization_revenue_keeps_currency_and_feedback_keeps_question_scale():
    rows = aggregate_rows("event-revenue", [
        (1, [dict(period="2026-10-12", currency="usd", net_amount=Decimal("1.10"))]),
        (2, [dict(period="2026-10-12", currency="usd", net_amount=Decimal("2.20")),
             dict(period="2026-10-12", currency="eur", net_amount=Decimal("9.99"))]),
    ], limit=10)
    assert {r["currency"]: r["net_amount"] for r in rows} == {"usd": Decimal("3.30"), "eur": Decimal("9.99")}
    scores = aggregate_rows("event-feedback-scores", [
        (1, [dict(event_id=1, title="A", period="2026-10-12", question_id="q", score_total=Decimal(5), score_count=1)]),
        (2, [dict(event_id=2, title="B", period="2026-10-12", question_id="q", score_total=Decimal(900), score_count=9)]),
    ], limit=10)
    assert [r["average_score"] for r in scores] == [Decimal(5), Decimal(100)]
