"""Read-only availability projections for other modules (Inventory Availability owns all quantity math).

Nothing here reserves, moves or writes a count. Callers outside inventory (the events equipment desk)
read these instead of re-deriving stock or outstanding quantities, so the one rule for "how many are
out" and "is there enough" lives with the module that changes those numbers.

* :func:`outstanding_units` -- units still with the borrower on one request, from the workflow's item
  counters (the same formula the loan limits use: issued - returned - damaged - missing);
* :func:`stock_warnings` / :func:`request_stock_warnings` -- advisory, never a refusal: units under
  repair, reserved individually tracked units no longer on the shelf, and asks larger than today's
  stock by the check acceptance makes.
"""

from collections import defaultdict

UNITS_UNDER_REPAIR = "units_under_repair"
RESERVED_UNITS_UNAVAILABLE = "reserved_units_unavailable"
INSUFFICIENT_STOCK = "insufficient_stock"


def item_outstanding(item):
    return max(0, item.issued_quantity - item.returned_quantity - item.damaged_quantity - item.missing_quantity)


def outstanding_units(request):
    """Units still with the borrower on one request (prefetch ``items`` to avoid a query per request)."""
    return sum(item_outstanding(item) for item in request.items.all())


def item_reserved(item, status):
    """Units held in ``reserved`` for one item: accepted but not yet issued.

    Issuing moves every accepted unit out of ``reserved``, so a loan that has been issued, closed or
    cancelled holds nothing; only an accepted request still waiting for handover holds stock.
    """
    return max(0, item.accepted_quantity - item.issued_quantity) if status == "accepted" else 0


def reserved_units(request):
    """Units one request still holds in reserve (prefetch ``items``)."""
    return sum(item_reserved(item, request.status) for item in request.items.all())


def _asset_counts(product_ids):
    from django.db.models import Count

    from apps.inventory.models import InventoryAsset
    if not product_ids:
        return defaultdict(dict)
    rows = (InventoryAsset.objects.filter(product_id__in=product_ids,
                                          status__in=(InventoryAsset.Status.AVAILABLE, InventoryAsset.Status.MAINTENANCE))
            .values("product_id", "status").annotate(n=Count("pk")))
    counts = defaultdict(dict)
    for row in rows:
        counts[row["product_id"]][row["status"]] = row["n"]
    return counts


def stock_warnings(products, requested):
    """``[(product, code, count)]`` for ``products`` (id -> product) given ``requested`` (id -> units asked).

    Today's stock only: nothing is forecast to a future window.
    """
    from apps.inventory.availability_requests import assert_individual_assets_available
    from apps.inventory.availability_types import InsufficientStock
    from apps.inventory.models import InventoryAsset, TrackingMode
    counts = _asset_counts([pk for pk, row in products.items() if row.tracking_mode == TrackingMode.INDIVIDUAL])
    warnings = []
    for pk, product in sorted(products.items()):
        individual = product.tracking_mode == TrackingMode.INDIVIDUAL
        on_shelf = counts[pk].get(InventoryAsset.Status.AVAILABLE, 0)
        repair = counts[pk].get(InventoryAsset.Status.MAINTENANCE, 0) if individual else product.needs_fix_quantity
        if repair:
            warnings.append((product, UNITS_UNDER_REPAIR, repair))
        if individual and on_shelf < product.reserved_quantity:
            warnings.append((product, RESERVED_UNITS_UNAVAILABLE, product.reserved_quantity - on_shelf))
        need = requested.get(pk, 0)
        if need:
            try:
                short = need > product.available_quantity
                assert_individual_assets_available(product, need)
            except InsufficientStock:
                short = True
            if short:
                warnings.append((product, INSUFFICIENT_STOCK, need))
    return warnings


def request_stock_warnings(held, asking):
    """:func:`stock_warnings` for the products of two request groups.

    ``held`` are requests whose units are already reserved (accepted): only their products are checked.
    ``asking`` are requests awaiting review: their requested units are summed per product and checked
    against today's stock by the same rule acceptance applies.
    """
    requested, products = defaultdict(int), {}
    for group, ask in ((held, False), (asking, True)):
        for request in group:
            for item in request.items.all():
                products[item.product_id] = item.product
                if ask:
                    requested[item.product_id] += item.requested_quantity
    return stock_warnings(products, requested)
