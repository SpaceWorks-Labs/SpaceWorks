from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone

from apps.boxes.models import QrCode, QrScanEvent
from apps.hardware_requests.models import HardwareRequest, HardwareRequestItem, HardwareRequestItemAsset, ReturnEvent
from apps.inventory.models import InventoryAsset
from apps.inventory.models_tracking import InventoryStockSnapshot
from apps.inventory.models_watch import InventoryWatch
from apps.operations.report_registry import report_definition
from apps.operations.reports import report_data
from apps.operations.reports_ab_loans import build_loan_throughput, build_most_lent, build_request_funnel
from apps.operations.reports_ab_stock import build_inventory_utilisation, build_stock_health, build_damaged_lost
from tests.operations.report_assertions import assert_report_disclosure_safe
from tests.return_helpers import make_member, make_product, make_return_evidence, make_space


pytestmark = pytest.mark.django_db


def enable(space, *modules):
    space.enabled_modules = sorted(set(space.enabled_modules) | set(modules) | {"reports"})
    space.save(update_fields=["enabled_modules"])


def loan(space, actor, product, *, at=None, status="issued", quantity=3, returned=0):
    at = at or timezone.now() - timedelta(days=10)
    row = HardwareRequest.objects.create(makerspace=space, requester=actor, requester_username=actor.username,
        status=status, issued_at=at, accepted_at=at - timedelta(hours=2),
        return_due_at=at + timedelta(days=1), closed_at=timezone.now() if status == "returned" else None)
    HardwareRequest.objects.filter(pk=row.pk).update(created_at=at - timedelta(hours=6))
    HardwareRequestItem.objects.create(request=row, product=product, requested_quantity=quantity,
        accepted_quantity=quantity, issued_quantity=quantity, returned_quantity=returned)
    return row


def seed_sources(space, actor, marker):
    """One real row per source so every catalog builder's isolation check is nonempty."""
    from apps.hardware_requests.models import PublicToolLoan, PublicProblemReport
    from apps.operations.models import QrPrintBatch, StockTransfer, StockTransferLine, StocktakeSession, StocktakeLine
    from apps.procurement.models import ToBuyItem
    from apps.machines.models import MachineConsumablePool
    from tests.analytics.ab_service_helpers import service
    from tests.test_machine_service_workflow import machine
    enable(space, "machines", "machine_service", "scanner", "asset_units", "guest_handover",
           "public_inventory", "request_workflow", "stock_transfers", "stocktake", "qr_print_batches", "procurement")
    product = make_product(space, name=marker, tracking_mode="individual", available_quantity=0)
    request = loan(space, actor, product)
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag=marker, status="issued")
    HardwareRequestItemAsset.objects.create(request_item=request.items.get(), asset=asset, issued_at=request.issued_at)
    qr = QrCode.objects.create(makerspace=space, target_type="asset", target_id=asset.pk)
    QrScanEvent.objects.create(makerspace=space, qr_code=qr, actor=actor, context="scanner_lookup")
    InventoryWatch.objects.create(makerspace=space, product=product, user=actor)
    QrPrintBatch.objects.create(makerspace=space, title=marker)
    transfer = StockTransfer.objects.create(makerspace=space, reason="Transfer")
    StockTransferLine.objects.create(transfer=transfer, product=product, quantity=1)
    take = StocktakeSession.objects.create(makerspace=space, status="completed", completed_at=timezone.now())
    StocktakeLine.objects.create(stocktake=take, product=product, variance_quantity=-1)
    item = ToBuyItem.objects.create(makerspace=space, name=marker, kind="hardware", quantity=1)
    direct = PublicToolLoan.objects.create(makerspace=space, request=request, requester=actor,
        target_type="asset", target_id=asset.pk, target_label=marker)
    PublicProblemReport.objects.create(makerspace=space, loan=direct, request=request, requester=actor, note="Problem")
    target = machine(space)
    pool = MachineConsumablePool.objects.create(makerspace=space, machine=target, material=marker,
        initial_grams=100, remaining_grams=50)
    service(space, target, pool, actor, quantity=2)
    return dict(product_id=product.pk, request_id=request.pk, asset_id=asset.pk,
                actor_id=actor.pk, pool_id=pool.pk, item_id=item.pk)


@pytest.mark.parametrize("grain,expected", [("day", "2026-10-12"), ("week", "2026-10-12"), ("month", "2026-10-01")])
def test_issue_time_local_calendar_and_top_five_plus_other(grain, expected):
    space = make_space("ab-issue-time")
    space.timezone = "Asia/Kolkata"
    space.save(update_fields=["timezone"])
    actor = make_member("ab-issue-manager", space)
    at = datetime(2026, 10, 11, 20, tzinfo=dt_timezone.utc)
    for index in range(7):
        product = make_product(space, name=f"Product {index}")
        loan(space, actor, product, at=at, quantity=index + 1)
    foreign = make_space("ab-issue-foreign")
    loan(foreign, actor, make_product(foreign, name="FOREIGN"), at=at, quantity=100)
    report = build_most_lent(space.pk, grain=grain)
    assert len(report.records) == 6
    assert {str(row["period"]) for row in report.records} == {expected}
    assert sum(row["total_quantity_lent"] for row in report.records) == 28
    assert next(row for row in report.records if row["product_name"] == "Other")["total_quantity_lent"] == 3
    assert_report_disclosure_safe(report.records)


def test_returns_use_return_events_even_when_request_closed_in_another_period():
    space = make_space("ab-return-time")
    actor = make_member("ab-return-manager", space)
    request = loan(space, actor, make_product(space), status="returned", returned=3)
    event = ReturnEvent.objects.create(makerspace=space, request=request, actor=actor,
        evidence=make_return_evidence(space, actor), remark="PRIVATE REMARK")
    start = event.created_at - timedelta(minutes=1)
    report = build_loan_throughput(space.pk, date_range=(start, start + timedelta(days=1)))
    assert sum(row["return_events"] for row in report.records) == 1
    assert sum(row["returned_units"] for row in report.records) == 3
    assert sum(row["issued_requests"] for row in report.records) == 0
    ReturnEvent.objects.create(makerspace=space, request=request, actor=actor,
        evidence=make_return_evidence(space, actor), remark="another partial return")
    report = build_loan_throughput(space.pk)
    assert sum(row["return_quantity_unknown_events"] for row in report.records) == 2
    assert sum(row["returned_units"] for row in report.records) == 0
    assert_report_disclosure_safe(report.records)


def test_observed_stock_gaps_and_weighted_utilisation_do_not_reconstruct_days():
    space = make_space("ab-observations")
    product = make_product(space, total_quantity=10, issued_quantity=2, available_quantity=8)
    for day, issued, total in (("2026-10-12", 1, 1), ("2026-10-14", 0, 9)):
        InventoryStockSnapshot.objects.create(makerspace=space, product=product, local_day=day,
            available=total - issued, issued=issued, total=total, out_of_stock=bool(issued), below_reorder=bool(issued))
    history = [row for row in build_inventory_utilisation(space.pk, grain="week").records if row["row_kind"] == "observed"]
    assert len(history) == 1 and history[0]["utilisation_percent"] == 10
    health = [row for row in build_stock_health(space.pk, grain="week").records if row["row_kind"] == "observed"]
    assert health[0]["days_observed"] == 2
    assert health[0]["days_observed_out_of_stock"] == 1
    assert_report_disclosure_safe(health)


def test_asset_damage_rates_and_summary_mix_are_counts_only():
    space = make_space("ab-assets")
    enable(space, "asset_units")
    actor = make_member("ab-assets-manager", space)
    product = make_product(space, tracking_mode="individual", available_quantity=7, damaged_quantity=2, lost_quantity=1)
    request = loan(space, actor, product)
    item = request.items.get()
    asset = InventoryAsset.objects.create(makerspace=space, product=product, asset_tag="A", status="damaged")
    HardwareRequestItemAsset.objects.create(request_item=item, asset=asset, issued_at=request.issued_at,
        returned_at=timezone.now(), outcome="damaged")
    report = report_definition("asset-usage").builder()(space.pk)
    assert report.records[0]["damaged_count"] == 1
    assert "holder" not in report.field_order
    damage = build_damaged_lost(space.pk).records[0]
    assert damage["damage_rate_percent"] == 20 and damage["loss_rate_percent"] == 10
    summary = report_data("summary", space.pk)
    assert summary["asset_damaged"] == summary["assets"] == 1
    assert_report_disclosure_safe(summary)


@pytest.mark.parametrize("grain", ["day", "week", "month"])
def test_qr_counts_target_and_hour_have_no_actor_but_actor_key_is_identity_bearing(grain):
    space = make_space("ab-qr")
    enable(space, "scanner")
    actor = make_member("ab-qr-manager", space)
    qr = QrCode.objects.create(makerspace=space, target_type="product", target_id=1)
    QrScanEvent.objects.create(makerspace=space, qr_code=qr, actor=actor, context="scanner_lookup")
    data = report_data("qr-scans", space.pk, grain=grain)["typed_rows"]
    assert sum(row["count"] for row in data) == 1
    assert data[0]["target_type"] == "product" and 0 <= data[0]["hour_of_week"] < 168
    assert "actor_id" not in data[0]
    actor_rows = report_data("qr-scan-actors", space.pk, actor=actor)["typed_rows"]
    assert actor_rows == [{"actor_id": actor.pk, "count": 1}]
    assert_report_disclosure_safe(data)


def test_overdue_and_longest_disclose_only_authorized_tenant_holders():
    space, foreign = make_space("ab-holders"), make_space("ab-holders-foreign")
    actor = make_member("ab-holder-manager", space)
    own = loan(space, actor, make_product(space))
    loan(foreign, actor, make_product(foreign))
    for key in ("overdue-loans", "longest-loans"):
        data = report_data(key, space.pk, actor=actor)
        holders = [row for row in data["typed_rows"] if row.get("request_id")]
        assert [row["request_id"] for row in holders] == [own.pk]
        assert_report_disclosure_safe(data, aggregate=False)


def test_request_funnel_and_approval_histogram_use_submission_cohorts():
    space = make_space("ab-funnel")
    actor = make_member("ab-funnel-manager", space)
    loan(space, actor, make_product(space), status="returned", returned=3)
    rows = build_request_funnel(space.pk, grain="week").records
    assert {row["stage"] for row in rows if row["row_kind"] == "funnel"} == {"requested", "accepted", "issued", "returned"}
    assert next(row for row in rows if row["row_kind"] == "approval_histogram")["approval_bucket"] == "1–24h"
    assert_report_disclosure_safe(rows)


def test_member_card_qr_counts_never_disclose_card_or_person_identifiers():
    space = make_space("ab-card-counts")
    enable(space, "scanner")
    actor = make_member("ab-card-manager", space)
    qr = QrCode.objects.create(makerspace=space, target_type="member_card", target_id=987654)
    QrScanEvent.objects.create(makerspace=space, qr_code=qr, actor=actor, context="member_lookup")
    rows = report_data("qr-scans", space.pk)["typed_rows"]
    assert rows[0]["target_type"] == "member_card" and rows[0]["target_id"] is None
    assert "987654" not in str(rows)
    assert_report_disclosure_safe(rows)
