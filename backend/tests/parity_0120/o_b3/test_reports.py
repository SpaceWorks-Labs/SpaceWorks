"""O-B3: cash in hand, revenue by plan, the renewal forecast and approval times against fixtures."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.makerspaces.models import MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.reports import report_data
from apps.payments.cash_handover import record_cash_handover
from apps.payments.models import Payment
from apps.payments.reconciliation import mark_offline
from tests.l5_local.helpers import dues, setup
from tests.return_helpers import settlement_details

pytestmark = pytest.mark.django_db


def test_the_four_reports_are_registered_tenant_local_with_a_title():
    for key in ("cash-in-hand", "membership-revenue-by-plan", "membership-renewal-forecast",
                "membership-approval-times"):
        definition = REPORT_REGISTRY[key]
        assert not definition.deployment_aggregate and definition.title


def test_cash_in_hand_subtracts_hand_overs_and_ignores_non_cash():
    space, manager, payer = setup("cash-hand", "billing.collection_sheet")
    for reference, method, amount in (("A", "cash", "100.00"), ("B", "cash", "50.00"), ("C", "upi", "30.00")):
        mark_offline(dues(space, payer, amount), manager, settlement_details(reference=reference, method=method))
    record_cash_handover(actor=manager, space=space, collector=manager, amount=Decimal("120.00"), currency="inr")
    row = report_data("cash-in-hand", space.pk, actor=manager)["typed_rows"][0]
    assert (row["received_cash"], row["handed_over"], row["cash_in_hand"]) == ("150.00", "120.00", "30.00")


def test_a_cash_handover_is_not_spending():
    space, manager, _payer = setup("cash-hand-spend", "billing.collection_sheet", "finance.ledger")
    record_cash_handover(actor=manager, space=space, collector=manager, amount=Decimal("10.00"), currency="inr")
    from apps.payments.finance_rows import money_rows
    assert not [row for row in money_rows(space) if row.column == "expenses"]


def test_revenue_by_plan_is_net_of_refunds_and_per_currency():
    space, manager, payer = setup("rev-plan", "membership", "membership.insights")
    plan = MembershipPlan.objects.create(makerspace=space, name="Gold", interval="yearly", amount=100, currency="inr")
    membership = MakerspaceMembership.objects.get(makerspace=space, user=payer)
    now = timezone.now()
    term = MembershipTerm.objects.create(membership=membership, plan=plan, starts_at=now,
                                         ends_at=now + timedelta(days=365))
    payment = Payment.objects.create(makerspace=space, subject_type=Payment.SubjectType.MEMBERSHIP_TERM_START,
                                     subject_id=term.pk, member=payer, amount=Decimal("100.00"), currency="inr",
                                     created_by=manager)
    mark_offline(payment, manager, settlement_details(reference="G"))
    rows = report_data("membership-revenue-by-plan", space.pk, actor=manager)["typed_rows"]
    assert rows[0]["plan_name"] == "Gold" and rows[0]["collected"] == "100.00" and rows[0]["net"] == "100.00"


def test_renewal_forecast_is_cumulative_and_skips_non_renewing_plans():
    space, manager, payer = setup("forecast", "membership", "membership.insights")
    rolling = MembershipPlan.objects.create(makerspace=space, name="Roll", interval="yearly", amount=100,
                                            renewal_amount=80, currency="inr")
    fixed = MembershipPlan.objects.create(makerspace=space, name="Fixed", interval="yearly", amount=10,
                                          currency="inr", plan_type="fixed_end",
                                          fixed_end_date=(timezone.now() + timedelta(days=20)).date())
    membership = MakerspaceMembership.objects.get(makerspace=space, user=payer)
    now = timezone.now()
    MembershipTerm.objects.create(membership=membership, plan=rolling, starts_at=now - timedelta(days=300),
                                  ends_at=now + timedelta(days=45))
    MembershipTerm.objects.create(membership=membership, plan=fixed, starts_at=now - timedelta(days=300),
                                  ends_at=now + timedelta(days=10))
    rows = {row["horizon_days"]: row
            for row in report_data("membership-renewal-forecast", space.pk, actor=manager)["typed_rows"]}
    assert rows[60]["terms_ending"] == 1 and rows[60]["expected_amount"] == "80.00"
    assert rows[90]["terms_ending"] == 1


def test_approval_times_use_nearest_rank_p90():
    from apps.operations.reports_approval_times import p90
    assert p90([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == 9 and p90([5]) == 5 and p90([]) is None
