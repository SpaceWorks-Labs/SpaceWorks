"""Disclosure, module, role, chart and organization contracts for the F/G lane."""

from datetime import timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from tests.accounts.account_factories import make_membership  # a term needs a community membership
from django.utils import timezone
from openpyxl import load_workbook

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace, MakerspaceMembership, MembershipPlan, MembershipTerm
from apps.makerspaces.module_install import install_module
from apps.operations.org_report_aggregate import COMBINE_FUNCTIONS, aggregate_rows
from apps.operations.org_report_scope import EXCLUDED_ORGANIZATION_REPORT_KEYS
from apps.operations.org_report_strategies import STRATEGIES
from apps.operations.report_condition_metrics import NUMERIC_FIELDS
from apps.operations.report_registry import report_definition
from apps.operations.report_scope import combined_report_scope
from apps.operations.report_validation import validate_report_definition
from apps.operations.org_reports import organization_report_data
from tests.fixed_roles.helpers import staff_account
from tests.module_helpers import disable_module
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.operations.test_finance_reports import cash_payment
from tests.payments.test_refunds import paid_deposit
from tests.return_helpers import authenticated_client, make_member, make_space

KEYS = ("membership-growth", "member-retention", "membership-revenue", "revenue-over-time",
        "payments-ageing", "payment-reconciliation", "cash-book")
MEMBERSHIP_KEYS = KEYS[:3]


@pytest.mark.parametrize("key", KEYS)
def test_counts_only_chart_and_organization_declarations(key):
    definition = report_definition(key)
    validate_report_definition(definition)
    assert not definition.identity_bearing and not definition.platform_only
    assert definition.deployment_aggregate and definition.schedulable
    assert key not in EXCLUDED_ORGANIZATION_REPORT_KEYS and key in COMBINE_FUNCTIONS
    assert set(STRATEGIES[key].total_fields) == set(definition.fields) - {"makerspace_id"}
    assert definition.chart_spec and definition.chart_spec["truncation"] is None
    if key not in ("payments-ageing", "payment-reconciliation", "member-retention"):
        assert set(definition.grains) == {"day", "week", "month"}
    if key not in MEMBERSHIP_KEYS:
        assert not definition.required_modules  # Core money survives rail removal.
        assert definition.chart_spec["partition"] == "currency"
    assert definition.required_action == (rbac.Action.MANAGE_MEMBERS if key in MEMBERSHIP_KEYS[:2] else rbac.Action.VIEW_FINANCE)  # decision 224a
    assert_report_disclosure_safe(definition.chart_spec)


def test_cohort_heatmap_and_numeric_threshold_fields():
    definition = report_definition("member-retention")
    assert definition.chart_hint == "heatmap"
    assert definition.chart_spec["series"] == ["cohort_month"]
    assert definition.chart_spec["x"]["field"] == "months_after_join"
    assert {"activated_members", "owed_amount", "waived_amount", "payment_count", "outstanding_amount"} <= NUMERIC_FIELDS


@pytest.mark.django_db
@pytest.mark.parametrize("key", KEYS)
def test_http_module_and_role_gates_and_artifact_disclosure(key):
    space = make_space("fg-contract")
    install_module(space, "membership")
    actor = make_member("fg-contract-owner", space)
    now = timezone.now()
    plan = MembershipPlan.objects.create(makerspace=space, name="Monthly", interval="monthly", amount=10)
    MembershipTerm.objects.create(membership=make_membership(actor, space), plan=plan,
                                  starts_at=now - timedelta(days=1), ends_at=now + timedelta(days=365))
    cash_payment(space, actor)
    paid_deposit(space, actor, status="pending", intent=None)
    client = authenticated_client(actor)
    route = f"/api/v1/admin/makerspace/{space.pk}/analytics/{key}"
    payload = client.get(route)
    assert payload.status_code == 200, payload.data
    assert_report_disclosure_safe(payload.data)
    assert set(payload.data["rows"][0]) <= set(report_definition(key).fields)
    for fmt in ("csv", "xlsx"):
        response = client.get(f"/api/v1/admin/makerspace/{space.pk}/reports/{key}/export?format={fmt}")
        assert response.status_code == 200
        content = b"".join(response.streaming_content) if response.streaming else response.content
        if fmt == "csv":
            assert_report_disclosure_safe(content.decode("utf-8-sig"))
        else:
            workbook = load_workbook(BytesIO(content), read_only=True)
            for sheet in workbook:
                assert_report_disclosure_safe(list(sheet.values))
            workbook.close()
    denied = staff_account(space, "fg-contract-handover", "handover")
    assert authenticated_client(denied).get(route).status_code in (403, 404)
    audit_reader = staff_account(space, "fg-contract-inventory", "inventory_manager")
    audit_response = authenticated_client(audit_reader).get(route)
    assert audit_response.status_code == 403  # decision 224a: the Inventory Manager manages no member area
    if key in MEMBERSHIP_KEYS:
        disable_module(space, "membership")
        assert client.get(route).status_code == 404
    else:
        # All amounts remain readable with the online rail and member login off.
        disable_module(space, "payments")
        disable_module(space, "member_accounts")
        assert not {"payments", "member_accounts", "mobile"} & set(space.enabled_modules)
        assert client.get(route).status_code == 200
    disable_module(space, "reports")
    assert client.get(route).status_code == 404


def test_org_retention_recomputes_from_summed_eligible_memberships():
    def row(eligible, retained):
        return dict(cohort_month="2025-01", months_after_join=3, cohort_members=eligible,
                    eligible_members=eligible, retained_members=retained, churned_members=eligible-retained, reactivated_members=0)
    result = aggregate_rows("member-retention", [(1, [row(1, 1)]), (2, [row(9, 0)])], limit=10)
    assert result[0]["retention_percent"] == Decimal("10.00")
    assert result[0]["eligible_members"] == 10
    assert_report_disclosure_safe(result)


def test_org_growth_counts_memberships_and_cash_never_merges_currency_or_method():
    result = aggregate_rows("membership-growth", [(1, [dict(period="2026-10-01", new_members=1,
        activated_members=2, revoked_members=1, active_members=7)]), (2, [dict(period="2026-10-01",
        new_members=3, activated_members=4, revoked_members=0, active_members=9)])], limit=1)
    assert result == [dict(period="2026-10-01", new_members=4, activated_members=6, revoked_members=1, active_members=16)]
    rows = [dict(period="2026-10-01", currency=currency, method=method,
                 collected_amount=Decimal(10), refunded_amount=Decimal(2), net_amount=Decimal(8))
            for currency, method in (("usd", "cash"), ("eur", "cash"), ("usd", "upi"))]
    result = aggregate_rows("cash-book", [(1, rows), (2, rows)], limit=10)
    assert len(result) == 3 and all(row["net_amount"] == 16 for row in result)


def test_org_membership_revenue_preserves_plan_identity_and_computes_weighted_arpu():
    def row(plan, members, mrr):
        return dict(period="2026-10-01", currency="usd", plan_id=plan, plan_name="Monthly",
                    recurring_members=members, mrr=Decimal(mrr), arr=Decimal(mrr)*12,
                    churned_members=0, reactivated_members=0)
    result = aggregate_rows("membership-revenue", [(1, [row(1, 1, 10), row(2, 1, 100)]),
                                                   (2, [row(1, 9, 180)])], limit=10)
    assert len(result) == 2
    assert result[0]["arpu"] == Decimal(19) and result[0]["mrr"] == 190
    assert result[1]["arpu"] == 100


def test_org_revenue_ageing_and_reconciliation_sum_full_partitions_before_limit():
    def revenue(rail):
        return dict(period="2026-10-01", currency="usd", subject_type="booking", rail=rail,
                    collected_amount=Decimal(10), refunded_amount=Decimal(2), owed_amount=Decimal(0),
                    waived_amount=Decimal(0), net_amount=Decimal(8))
    rows = [(1, [revenue("offline"), revenue("online")]), (2, [revenue("offline")])]
    result = aggregate_rows("revenue-over-time", rows, limit=1)
    assert result[0]["rail"] == "offline" and result[0]["net_amount"] == 16
    age = dict(currency="usd", age_bucket="90+", payment_count=1, outstanding_amount=Decimal(7))
    result = aggregate_rows("payments-ageing", [(1, [age]), (2, [age])], limit=10)
    assert result == [dict(currency="usd", age_bucket="90+", payment_count=2, outstanding_amount=Decimal(14))]
    row = dict(currency="usd", subject_type="booking", status="pending", settlement_method="",
               payment_count=1, amount_total=Decimal(7), outstanding_amount=Decimal(7), refunded_amount=Decimal(0))
    result = aggregate_rows("payment-reconciliation", [(1, [row]), (2, [row])], limit=10)
    assert result[0]["payment_count"] == 2 and result[0]["outstanding_amount"] == 14
    assert_report_disclosure_safe(result)


@pytest.mark.django_db
@pytest.mark.parametrize("key", KEYS)
def test_organization_orchestration_projects_only_declared_counts_and_preserves_breakdown(key):
    own, other = make_space("fg-org-own"), make_space("fg-org-other")
    for space in (own, other):
        install_module(space, "membership")
        actor = make_member(f"fg-org-owner-{space.pk}", space)
        cash_payment(space, actor)
        paid_deposit(space, actor, status="pending", intent=None)
        plan = MembershipPlan.objects.create(makerspace=space, name="Monthly", interval="monthly", amount=10)
        MembershipTerm.objects.create(membership=make_membership(actor, space), plan=plan,
            starts_at=timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=365))
    definition = report_definition(key)
    scope = combined_report_scope(Makerspace.objects.filter(pk__in=(own.pk, other.pk)))
    payload = organization_report_data(definition, scope, limit=10, grain="week")
    assert {row["makerspace_id"] for row in payload["breakdown"]} == {own.pk, other.pk}
    assert payload["total"]["rows"]
    assert all(set(row) <= set(definition.fields) for row in payload["total"]["rows"])
    assert_report_disclosure_safe(payload)


@pytest.mark.django_db
@pytest.mark.parametrize("key", KEYS)
def test_space_staff_keep_local_report_access(key):
    space = make_space("fg-hidden")
    install_module(space, "membership")
    actor = make_member("fg-hidden-owner", space)
    plan = MembershipPlan.objects.create(makerspace=space, name="Monthly", interval="monthly", amount=10)
    MembershipTerm.objects.create(membership=make_membership(actor, space), plan=plan,
        starts_at=timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=365))
    cash_payment(space, actor)
    paid_deposit(space, actor, status="pending", intent=None)
    client = authenticated_client(actor)
    response = client.get(f"/api/v1/admin/makerspace/{space.pk}/analytics/{key}")
    assert response.status_code == 200, response.data
    assert response.data["typed_rows"]
    assert_report_disclosure_safe(response.data)
