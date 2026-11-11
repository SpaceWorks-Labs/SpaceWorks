"""Advisory equipment warnings for an event's desk (decision 216). Read-only, never a refusal.

Read from the inventory owner's stored counters and asset statuses only; no quantity is
reserved, moved or recomputed here, and the request workflow still decides at accept/issue:

* `units_under_repair`: units of a product the event's loans use are on the needs-fix shelf
  (counted products) or in `maintenance` status (individually tracked units);
* `reserved_units_unavailable`: an individually tracked product has fewer AVAILABLE units on
  the shelf than it holds reserved, so an accepted event loan may not be issuable in full;
* `insufficient_stock`: requests awaiting review ask for more than is available now, by the
  same check acceptance makes (`availability.assert_individual_assets_available` plus the
  stored `available_quantity`).

Stock is today's: availability is not forecast to the event's window.
"""

from collections import defaultdict

MAX_WARNINGS = 50


def _asset_counts(product_ids):
    from django.db.models import Count
    from apps.inventory.models import InventoryAsset
    rows = (InventoryAsset.objects.filter(product_id__in=product_ids,
                                          status__in=(InventoryAsset.Status.AVAILABLE, InventoryAsset.Status.MAINTENANCE))
            .values("product_id", "status").annotate(n=Count("pk")))
    counts = defaultdict(dict)
    for row in rows:
        counts[row["product_id"]][row["status"]] = row["n"]
    return counts


def equipment_warnings(ready, awaiting):
    """Warnings for the products of ready (accepted) and awaiting-review event loans."""
    from apps.inventory.availability import InsufficientStock, assert_individual_assets_available
    from apps.inventory.models import InventoryAsset, TrackingMode
    requested, products = defaultdict(int), {}
    for group, asking in ((ready, False), (awaiting, True)):
        for request in group:
            for item in request.items.all():
                products[item.product_id] = item.product
                if asking:
                    requested[item.product_id] += item.requested_quantity
    counts = _asset_counts([pk for pk, row in products.items() if row.tracking_mode == TrackingMode.INDIVIDUAL])
    warnings = []
    for pk, product in sorted(products.items()):
        individual = product.tracking_mode == TrackingMode.INDIVIDUAL
        repair = counts[pk].get(InventoryAsset.Status.MAINTENANCE, 0) if individual else product.needs_fix_quantity
        if repair:
            warnings.append(_row(product, "units_under_repair", repair))
        if individual and counts[pk].get(InventoryAsset.Status.AVAILABLE, 0) < product.reserved_quantity:
            warnings.append(_row(product, "reserved_units_unavailable",
                                 product.reserved_quantity - counts[pk].get(InventoryAsset.Status.AVAILABLE, 0)))
        need = requested.get(pk, 0)
        if need:
            try:
                short = need > product.available_quantity
                assert_individual_assets_available(product, need)
            except InsufficientStock:
                short = True
            if short:
                warnings.append(_row(product, "insufficient_stock", need))
    return warnings[:MAX_WARNINGS]


def _row(product, code, count):
    return {"product_id": product.pk, "product_name": product.name, "code": code, "count": count}
