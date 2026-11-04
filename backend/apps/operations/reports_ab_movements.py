"""Stock movements, stocktake observations and QR print batch trends."""

from apps.makerspaces.platform import module_enabled
from apps.operations.models import QrPrintBatch, StockTransferLine, StocktakeLine
from apps.operations.reports_ab_common import dated, result, spaces


TRANSFER_FIELDS = ("period", "source_makerspace_id", "destination_makerspace_id", "status", "quantity", "line_count")
VARIANCE_FIELDS = ("period", "product_id", "asset_id", "item_label", "expected_quantity", "counted_quantity", "variance_quantity")
CONTROL_FIELDS = ("period", "module_key", "metric_key", "dimension", "count", "quantity",
                  "rate_percent", "last_activity_at", "rate_numerator", "rate_denominator")


def build_stock_transfers(makerspace_id, *, limit=None, date_range=None, grain="day"):
    from django.db.models import Count, Sum
    records = []
    selected = spaces(makerspace_id, "stock_transfers")
    allowed = {space.pk for space in selected}
    for space in selected:
        qs = dated(StockTransferLine.objects.filter(transfer__makerspace=space), "transfer__created_at",
                   space, date_range, grain)
        for row in qs.values("report_period", "transfer__source_makerspace_id", "transfer__destination_makerspace_id",
                             "transfer__status").annotate(quantity=Sum("quantity"), line_count=Count("pk")):
            # A flow endpoint is disclosed only when it is already in the authorized scope.
            records.append(dict(makerspace_id=space.pk, period=row["report_period"].date(),
                source_makerspace_id=row["transfer__source_makerspace_id"] if row["transfer__source_makerspace_id"] in allowed else None,
                destination_makerspace_id=row["transfer__destination_makerspace_id"] if row["transfer__destination_makerspace_id"] in allowed else None,
                status=row["transfer__status"], quantity=row["quantity"], line_count=row["line_count"]))
    return result(TRANSFER_FIELDS, records, makerspace_id, limit)


def build_stocktake_variance(makerspace_id, *, limit=None, date_range=None, grain="day"):
    from django.db.models import Sum
    records = []
    for space in spaces(makerspace_id, "stocktake"):
        qs = dated(StocktakeLine.objects.filter(stocktake__makerspace=space,
                    stocktake__status__in=("completed", "approved", "applied")),
                   "stocktake__completed_at", space, date_range, grain)
        for row in qs.values("report_period", "product_id", "asset_id", "product__name", "asset__product__name", "asset__asset_tag").annotate(
            expected_quantity=Sum("expected_quantity"), counted_quantity=Sum("counted_quantity"),
            variance_quantity=Sum("variance_quantity"),
        ):
            product_label = row.pop("product__name")
            asset_label = " ".join(filter(None, (row.pop("asset__product__name"), row.pop("asset__asset_tag"))))
            label = product_label or asset_label
            records.append(dict(makerspace_id=space.pk, period=row.pop("report_period").date(), item_label=label, **row))
    records.sort(key=lambda row: (-abs(row["variance_quantity"]), str(row["product_id"]), str(row["asset_id"])))
    return result(VARIANCE_FIELDS, records, makerspace_id, limit)


def build_inventory_control(makerspace_id, *, limit=None, date_range=None, grain="day"):
    from django.db.models import Count
    from apps.operations.reports_inventory_control import build_inventory_control as legacy
    from apps.inventory.models import InventoryProduct
    from apps.boxes.models import Box
    records = []
    for space in spaces(makerspace_id):
        # Preserve the existing optional module sections and give each rate its denominator.
        for source in legacy(space.pk).records:
            row = dict(source, makerspace_id=space.pk, period=None, rate_numerator=0, rate_denominator=0)
            if row["metric_key"] == "visibility":
                row["rate_numerator"] = row["count"]
                row["rate_denominator"] = InventoryProduct.objects.filter(makerspace=space, is_archived=False).count()
            elif row["metric_key"] == "containers":
                row["rate_numerator"] = Box.objects.filter(makerspace=space, is_active=True).count()
                row["rate_denominator"] = row["count"]
            records.append(row)
        if module_enabled(space, "qr_print_batches"):
            qs = dated(QrPrintBatch.objects.filter(makerspace=space), "created_at", space, date_range, grain)
            # Aggregate batch counts separately: joining items multiplies batches.
            for row in qs.values("report_period", "status").annotate(count=Count("pk", distinct=True), quantity=Count("items")):
                records.append(dict(makerspace_id=space.pk, period=row["report_period"].date(),
                    module_key="qr_print_batches", metric_key="batch_trend", dimension=row["status"],
                    count=row["count"], quantity=row["quantity"], rate_percent=None,
                    last_activity_at=None, rate_numerator=0, rate_denominator=0))
    return result(CONTROL_FIELDS, records, makerspace_id, limit)
