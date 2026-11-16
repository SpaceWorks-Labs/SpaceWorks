"""Money analytics preserve ledger corrections, local dates and currency partitions."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from apps.operations.reports import report_data, report_rows
from apps.operations.reports_finance import build_cash_book, build_revenue_over_time
from apps.operations.reports_payments_ageing import AGE_BUCKETS, build_payments_ageing
from apps.operations.views_report_helpers import date_range_from_dates
from apps.payments.models import Payment
from apps.payments.reconciliation import amend_settlement
from apps.payments.services_refunds_offline import amend_offline_refund, record_offline_refund
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.operations.test_finance_reports import cash_payment
from tests.payments.test_billing_due_p5 import new_charge
from tests.payments.test_refunds import paid_deposit
from tests.return_helpers import make_member, make_space, settlement_details

pytestmark = pytest.mark.django_db
NOW = datetime(2026, 10, 12, 12, tzinfo=UTC)


@pytest.mark.parametrize("days,bucket", [(0, "0-30"), (30, "0-30"), (31, "31-60"),
    (60, "31-60"), (61, "61-90"), (90, "61-90"), (91, "90+"), (-10, "0-30")])
def test_ageing_bucket_boundaries_use_due_date_in_local_calendar(days, bucket):
    space = make_space("fg-age-boundaries")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    # Membership dues are owed by a member account (account kinds), never by staff.
    actor = make_member("fg-age-member", space, membership_role="member", role="requester")
    # The ledger snapshots due_at on insert and refuses subsequent changes.
    payment = new_charge(space, actor, due_at=NOW - timedelta(days=days))
    Payment.objects.filter(pk=payment.pk).update(created_at=NOW - timedelta(days=120))
    result = build_payments_ageing(space.pk, now=NOW)
    assert [row["age_bucket"] for row in result.records] == list(AGE_BUCKETS)
    assert sum(row["outstanding_amount"] for row in result.records) == Decimal(10)
    assert next(row for row in result.records if row["age_bucket"] == bucket)["payment_count"] == 1
    assert_report_disclosure_safe(result.records)


def test_ageing_falls_back_to_creation_omits_terminal_and_foreign_charges_and_keeps_currencies():
    own, other = make_space("fg-age-own"), make_space("fg-age-foreign")
    actor = make_member("fg-age-owner", own)
    foreign = make_member("fg-age-stranger", other)
    for space, staff, currency, status in ((own, actor, "usd", "pending"),
        (own, actor, "eur", "pending"), (own, actor, "usd", "waived"), (other, foreign, "usd", "pending")):
        payment = paid_deposit(space, staff, status="pending", intent=None)
        Payment.objects.filter(pk=payment.pk).update(created_at=NOW - timedelta(days=61), currency=currency, status=status)
    rows = build_payments_ageing(own.pk, now=NOW, actor=actor).records
    assert sum(row["payment_count"] for row in rows) == 2
    assert {row["currency"] for row in rows} == {"usd", "eur"}
    assert all(row["outstanding_amount"] in (0, Decimal(10)) for row in rows)
    assert build_payments_ageing(other.pk, actor=actor).records == []
    aggregate = build_payments_ageing(None, now=NOW, actor=actor).records
    assert aggregate and {row["makerspace_id"] for row in aggregate} == {own.pk}
    assert_report_disclosure_safe(aggregate)
    assert build_payments_ageing(own.pk, date_range=(NOW - timedelta(days=10), NOW), now=NOW).records == []


@pytest.mark.parametrize("grain,period", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_revenue_rail_comes_from_settlement_not_payment_vendor(grain, period):
    space = make_space("fg-revenue-rail")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    actor = make_member("fg-revenue-staff", space)
    # A Stripe-attributed charge received in cash is still an offline collection.
    cash_payment(space, actor, at=datetime(2026, 10, 11, 20, tzinfo=UTC))
    online = paid_deposit(space, actor, intent=None, amount="7.00")
    Payment.objects.filter(pk=online.pk).update(updated_at=datetime(2026, 10, 11, 20, tzinfo=UTC))
    pending = paid_deposit(space, actor, status="pending", intent=None, amount="3.00")
    Payment.objects.filter(pk=pending.pk).update(created_at=datetime(2026, 10, 11, 20, tzinfo=UTC))
    window = date_range_from_dates(date(2026, 10, 12), date(2026, 10, 12))
    rows = build_revenue_over_time(space.pk, grain=grain, date_range=window, actor=actor).records
    by_rail = {row["rail"]: row for row in rows}
    assert {row["period"] for row in rows} == {period}
    assert by_rail["offline"]["collected_amount"] == Decimal(10)
    assert by_rail["online"]["collected_amount"] == Decimal(7)
    assert by_rail["unallocated"]["owed_amount"] == Decimal(3)
    assert_report_disclosure_safe(rows)


def test_revenue_refund_and_settlement_corrections_carry_money_once():
    space = make_space("fg-corrections")
    actor = make_member("fg-correction-staff", space)
    payment = cash_payment(space, actor)
    amend_settlement(actor=actor, makerspace_id=space.pk, payment_id=payment.pk,
                     settlement=settlement_details(method="upi"))
    refund = record_offline_refund(payment, amount="4.00", reason="Returned", actor=actor,
                                  receipt={"method": "cash", "reference": "first", "refunded_at": NOW})
    amend_offline_refund(payment, refund_id=refund.pk, actor=actor,
                         receipt={"method": "upi", "reference": "corrected", "refunded_at": NOW})
    rows = build_revenue_over_time(space.pk).records
    assert {row["rail"] for row in rows} == {"offline"}
    assert sum(row["collected_amount"] for row in rows) == 10
    assert sum(row["refunded_amount"] for row in rows) == 4
    assert sum(row["net_amount"] for row in rows) == 6
    cash = build_cash_book(space.pk).records
    assert {row["method"] for row in cash} == {"upi"}
    assert sum(row["net_amount"] for row in cash) == 6
    assert_report_disclosure_safe(report_data("revenue-over-time", space.pk, actor=actor))


@pytest.mark.parametrize("key", ["revenue-over-time", "payments-ageing", "payment-reconciliation", "cash-book"])
def test_payment_reports_tenant_isolation_and_deployment_rows(key):
    own, other = make_space("fg-payment-scope"), make_space("fg-payment-other")
    actor = make_member("fg-payment-owner", own)
    cash_payment(own, actor)
    paid_deposit(own, actor, status="pending", intent=None)
    cash_payment(other, make_member("fg-payment-stranger", other), amount="999.00")
    payload = report_data(key, own.pk, actor=actor)
    assert "999.00" not in str(payload)
    foreign = report_data(key, other.pk, actor=actor)
    assert foreign["typed_rows"] == []
    aggregate = report_data(key, actor=actor)
    assert aggregate["typed_rows"]
    assert {row["makerspace_id"] for row in aggregate["typed_rows"]} == {own.pk}
    assert_report_disclosure_safe(payload)
    assert_report_disclosure_safe(aggregate)
    assert_report_disclosure_safe(report_rows(key, own.pk, actor=actor))
