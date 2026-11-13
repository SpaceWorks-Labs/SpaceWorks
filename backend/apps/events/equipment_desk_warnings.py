"""Advisory equipment warnings for an event's desk (decision 216). Read-only, never a refusal.

The quantity rules are Inventory Availability's (`inventory.availability.stock_warnings`); this module
only gathers the event's products and asks, then shapes the rows for the desk:

* `units_under_repair`: units of a product the event's loans use are on the needs-fix shelf
  (counted products) or in `maintenance` status (individually tracked units);
* `reserved_units_unavailable`: an individually tracked product has fewer AVAILABLE units on
  the shelf than it holds reserved, so an accepted event loan may not be issuable in full;
* `insufficient_stock`: requests awaiting review ask for more than is available now, by the
  same check acceptance makes.

Stock is today's: availability is not forecast to the event's window.
"""

MAX_WARNINGS = 50


def equipment_warnings(ready, awaiting):
    """Warnings for the products of ready (accepted) and awaiting-review event loans."""
    from apps.inventory.availability import request_stock_warnings
    return [_row(product, code, count) for product, code, count in request_stock_warnings(ready, awaiting)][:MAX_WARNINGS]


def _row(product, code, count):
    return {"product_id": product.pk, "product_name": product.name, "code": code, "count": count}
