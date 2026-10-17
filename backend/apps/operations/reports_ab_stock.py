"""Current stock and observed stock history. Missing observation days remain gaps."""

from django.db.models import Count, Sum
from django.utils import timezone

from apps.hardware_requests.models import HardwareRequest
from apps.inventory.models import InventoryAsset, InventoryProduct
from apps.inventory.models_tracking import InventoryStockSnapshot
from apps.makerspaces.platform import module_enabled
from apps.operations.reports_ab_assets import asset_records
from apps.operations.reports_ab_common import bucket, percent, result, spaces


UTIL_FIELDS = ("row_kind", "period", "product_id", "product_name", "asset_id", "issued_quantity",
               "total_quantity", "days_on_loan", "window_days", "utilisation_percent")
HEALTH_FIELDS = ("row_kind", "period", "product_id", "product_name", "out_of_stock", "below_reorder",
                 "days_observed", "days_observed_out_of_stock")
DAMAGE_FIELDS = ("product_id", "product_name", "damaged_quantity", "lost_quantity", "total_quantity",
                 "damage_rate_percent", "loss_rate_percent")
SUMMARY_FIELDS = ("products", "assets", "active_loans", "available_quantity", "issued_quantity",
                  "damaged_quantity", "missing_quantity", "asset_available", "asset_reserved", "asset_issued",
                  "asset_damaged", "asset_lost", "asset_maintenance", "asset_retired")


def observations(space, date_range):
    qs = InventoryStockSnapshot.objects.filter(makerspace=space).select_related("product")
    if date_range:
        from zoneinfo import ZoneInfo
        for bound, lookup in zip(date_range, ("gte", "lt")):
            if bound:
                qs = qs.filter(**{f"local_day__{lookup}": bound.astimezone(ZoneInfo(space.timezone)).date()})
    return qs


def build_inventory_utilisation(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in spaces(makerspace_id, "public_inventory"):
        for product in InventoryProduct.objects.filter(makerspace=space, is_archived=False):
            records.append(dict(makerspace_id=space.pk, row_kind="current", period=bucket(timezone.now(), space, "day"),
                product_id=product.pk, product_name=product.name, issued_quantity=product.issued_quantity,
                total_quantity=product.total_quantity,
                utilisation_percent=percent(product.issued_quantity, product.total_quantity)))
        groups = {}
        for snap in observations(space, date_range).iterator():
            period = bucket(snap.local_day, space, grain)
            row = groups.setdefault((period, snap.product_id), dict(makerspace_id=space.pk,
                row_kind="observed", period=period, product_id=snap.product_id, product_name=snap.product.name,
                issued_quantity=0, total_quantity=0))
            # Stock-days give a weighted period utilisation, never a sum of daily percentages.
            row["issued_quantity"] += snap.issued
            row["total_quantity"] += snap.total
        for row in groups.values():
            row["utilisation_percent"] = percent(row["issued_quantity"], row["total_quantity"])
            records.append(row)
        if module_enabled(space, "asset_units") and module_enabled(space, "request_workflow"):
            records.extend(dict(row, row_kind="asset", period=None) for row in asset_records(space, date_range))
    return result(UTIL_FIELDS, records, makerspace_id, limit,
        meta={"basis": "Current stock percentage; trend is issued stock-days divided by total stock-days on observed days; assets use loan days divided by window days."})


def build_stock_health(makerspace_id, *, limit=None, date_range=None, grain="day"):
    records = []
    for space in spaces(makerspace_id, "public_inventory"):
        for product in InventoryProduct.objects.filter(makerspace=space, is_archived=False):
            records.append(dict(makerspace_id=space.pk, row_kind="current", period=None, product_id=product.pk,
                product_name=product.name, out_of_stock=int(product.available_quantity <= 0),
                below_reorder=int(product.available_quantity < product.reorder_point),
                days_observed=0, days_observed_out_of_stock=0))
        groups = {}
        for snap in observations(space, date_range).iterator():
            key = (bucket(snap.local_day, space, grain), snap.product_id)
            row = groups.setdefault(key, dict(makerspace_id=space.pk, row_kind="observed", period=key[0],
                product_id=snap.product_id, product_name=snap.product.name, out_of_stock=0,
                below_reorder=0, days_observed=0, days_observed_out_of_stock=0))
            row["days_observed"] += 1
            row["days_observed_out_of_stock"] += int(snap.out_of_stock)
            row["out_of_stock"] += int(snap.out_of_stock)
            row["below_reorder"] += int(snap.below_reorder)
        records.extend(groups.values())
    return result(HEALTH_FIELDS, records, makerspace_id, limit,
        meta={"basis": "Days observed out of stock. Missing daily snapshots remain gaps; observed counts measure product-days."})


def build_damaged_lost(makerspace_id, *, limit=None, date_range=None):
    rows = []
    for space in spaces(makerspace_id, "public_inventory"):
        for product in InventoryProduct.objects.filter(makerspace=space, is_archived=False):
            rows.append(dict(makerspace_id=space.pk, product_id=product.pk, product_name=product.name,
                damaged_quantity=product.damaged_quantity, lost_quantity=product.lost_quantity,
                total_quantity=product.total_quantity,
                damage_rate_percent=percent(product.damaged_quantity, product.total_quantity),
                loss_rate_percent=percent(product.lost_quantity, product.total_quantity)))
    return result(DAMAGE_FIELDS, rows, makerspace_id, limit,
        meta={"basis": "Current damaged or lost stock divided by current total stock, per product."})


def build_summary(makerspace_id, *, limit=None, date_range=None):
    rows = []
    for space in spaces(makerspace_id, "public_inventory"):
        products = InventoryProduct.objects.filter(makerspace=space, is_archived=False)
        row = {field: 0 for field in SUMMARY_FIELDS}
        row.update(makerspace_id=space.pk, products=products.count())
        for field in ("available_quantity", "issued_quantity", "damaged_quantity", "lost_quantity"):
            row["missing_quantity" if field == "lost_quantity" else field] = products.aggregate(n=Sum(field))["n"] or 0
        if module_enabled(space, "request_workflow"):
            row["active_loans"] = HardwareRequest.objects.filter(makerspace=space,
                status__in=("issued", "partially_returned")).count()
        if module_enabled(space, "asset_units"):
            for status in InventoryAsset.objects.filter(makerspace=space, product__is_archived=False
                                                        ).values("status").annotate(n=Count("pk")):
                row[f"asset_{status['status']}"] = status["n"]
                row["assets"] += status["n"]
        rows.append(row)
    if makerspace_id is not None:
        return {field: rows[0][field] if rows else 0 for field in SUMMARY_FIELDS}
    return result(SUMMARY_FIELDS, rows, makerspace_id, limit)
