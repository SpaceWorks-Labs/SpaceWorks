"""Observe availability edges while the availability service holds the product lock."""

from apps.integrations.notifications_research import safe_adapter


def save_stock_change(product, *, update_fields):
    point = product.reorder_point
    if "available_quantity" not in update_fields:
        product.save(update_fields=update_fields)
        return
    # Read the committed-before value under the caller's existing row lock. Comparing
    # against the database also handles stale instances and repeated writes in one txn.
    previous = type(product).objects.values_list("available_quantity", flat=True).get(pk=product.pk)
    product.save(update_fields=update_fields)
    from .notify_me import availability_rose
    availability_rose(product, previous)
    if not product.is_archived and point > 0 and previous > point >= product.available_quantity:
        notify_low_stock(product)


@safe_adapter
def notify_low_stock(product):
    from .notifications_p2 import notify_stock
    return notify_stock(product)
