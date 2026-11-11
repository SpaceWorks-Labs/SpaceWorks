from datetime import timedelta

import pytest
from django.utils import timezone

from apps.hardware_requests.models import PublicProblemReport, PublicToolLoan
from apps.inventory.models_watch import InventoryWatch
from apps.operations.models import QrPrintBatch, StockTransfer, StockTransferLine, StocktakeSession, StocktakeLine
from apps.operations.org_report_aggregate import aggregate_rows
from apps.operations.reports_ab_activity import build_problem_reports, build_inventory_watch_demand
from apps.operations.reports_ab_movements import build_inventory_control, build_stock_transfers, build_stocktake_variance
from apps.operations.reports_ab_procurement import build_procurement_performance
from apps.procurement.models import ToBuyItem
from tests.analytics.test_ab_inventory_m1f2 import enable, loan
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import make_member, make_product, make_space


pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_stock_transfers_and_stocktake_variance_respect_tenant_scope(grain):
    space, other = make_space("ab-movements"), make_space("ab-movements-other")
    enable(space, "stock_transfers", "stocktake")
    product = make_product(space)
    transfer = StockTransfer.objects.create(makerspace=space, source_makerspace=space,
        destination_makerspace=other, reason="PRIVATE REASON")
    StockTransferLine.objects.create(transfer=transfer, product=product, quantity=4)
    foreign = StockTransfer.objects.create(makerspace=other, reason="FOREIGN")
    StockTransferLine.objects.create(transfer=foreign, product=make_product(other), quantity=100)
    take = StocktakeSession.objects.create(makerspace=space, status="completed", completed_at=timezone.now())
    StocktakeLine.objects.create(stocktake=take, product=product, expected_quantity=10, counted_quantity=7,
        variance_quantity=-3, notes="PRIVATE NOTES")
    transfer_rows = build_stock_transfers(space.pk, grain=grain).records
    assert len(transfer_rows) == 1 and transfer_rows[0]["quantity"] == 4
    assert transfer_rows[0]["destination_makerspace_id"] is None
    variance = build_stocktake_variance(space.pk, grain=grain).records
    assert len(variance) == 1 and variance[0]["variance_quantity"] == -3
    assert_report_disclosure_safe(transfer_rows)
    assert_report_disclosure_safe(variance)


def test_batch_trend_and_retained_optional_sections_are_module_gated():
    space = make_space("ab-print-batch")
    enable(space, "qr_print_batches")
    QrPrintBatch.objects.create(makerspace=space, title="PRIVATE LABEL")
    records = build_inventory_control(space.pk, grain="week").records
    assert sum(row["count"] for row in records if row["metric_key"] == "batch_trend") == 1
    space.enabled_modules.remove("qr_print_batches")
    space.save(update_fields=["enabled_modules"])
    assert not any(row["module_key"] == "qr_print_batches" for row in build_inventory_control(space.pk).records)
    assert_report_disclosure_safe(records)


def test_problem_open_and_resolution_times_and_watch_counts_exclude_private_content():
    space = make_space("ab-problems")
    enable(space, "guest_handover")
    actor = make_member("ab-problem-manager", space)
    product = make_product(space, available_quantity=0)
    request = loan(space, actor, product)
    direct = PublicToolLoan.objects.create(makerspace=space, requester=actor, request=request,
        target_type="product", target_id=product.pk, target_label=product.name)
    now = timezone.now()
    report = PublicProblemReport.objects.create(makerspace=space, requester=actor, request=request,
        loan=direct, note="PRIVATE NOTE", outcome="no_issue", resolved_at=now + timedelta(hours=2))
    PublicProblemReport.objects.filter(pk=report.pk).update(created_at=now)
    rows = build_problem_reports(space.pk).records
    assert sum(row["opened_count"] for row in rows) == sum(row["resolved_count"] for row in rows) == 1
    assert sum(row["resolution_hours"] for row in rows) == 2
    InventoryWatch.objects.create(makerspace=space, user=actor, product=product)
    watch = build_inventory_watch_demand(space.pk).records
    assert watch[0]["waiting_count"] == 1
    assert "PRIVATE" not in str(rows) and "requester" not in str(watch)
    assert_report_disclosure_safe(rows)
    assert_report_disclosure_safe(watch)


def test_procurement_lead_histogram_and_unknown_currency_cannot_merge_purchases():
    space = make_space("ab-procurement")
    enable(space, "procurement")
    now = timezone.now()
    for price in (2, 4):
        ToBuyItem.objects.create(makerspace=space, kind="hardware", name="Same label", quantity=3,
            actual_unit_cost=price, ordered_at=now + timedelta(hours=1), received_at=now + timedelta(hours=3))
    rows = build_procurement_performance(space.pk, grain="month").records
    assert len(rows) == 2
    assert {row["currency"] for row in rows} == {"unknown"}
    assert {row["lead_time_bucket"] for row in rows} == {"1–24h"}
    combined = aggregate_rows("procurement-performance", [(space.pk, rows)], limit=100)
    assert len(combined) == 2 and sum(row["receive_samples"] for row in combined) == 2
    assert_report_disclosure_safe(rows)
