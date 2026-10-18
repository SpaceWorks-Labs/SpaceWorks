"""Observe availability edges while the availability service holds the product lock."""

from django.db import transaction

from .models import InventoryProduct
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


@transaction.atomic
def observe_stock(makerspace, *, now):
    from zoneinfo import ZoneInfo
    from django.utils import timezone
    from apps.audit.services import record
    from apps.accounts import rbac
    from .models_tracking import InventoryStockSnapshot

    day = timezone.localdate(now, ZoneInfo(makerspace.timezone))
    products = rbac.scope_for_scheduled_work(
        InventoryProduct.objects.select_for_update().filter(is_archived=False),
        makerspace_id=makerspace.pk,
    )
    count = 0
    for product in products.order_by("pk").iterator(chunk_size=500):
        _, created = InventoryStockSnapshot.objects.get_or_create(
            makerspace=makerspace, product=product, local_day=day,
            defaults={"available": product.available_quantity, "issued": product.issued_quantity,
                      "total": product.total_quantity, "out_of_stock": product.available_quantity <= 0,
                      "below_reorder": product.available_quantity < product.reorder_point},
        )
        count += int(created)
    if count:
        record(None, "inventory.stock_observed", makerspace=makerspace,
               meta={"local_day": day.isoformat(), "product_count": count})
    return count
