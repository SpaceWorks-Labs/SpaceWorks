"""Reservation releases and waitlist holds: the only reserved<->available moves outside
accept/issue. Every function row-locks products in pk order and refuses to drive any
bucket below zero, so concurrent holds can never oversell."""

from django.db import connection

from apps.inventory.availability_stock import save_stock_change
from apps.inventory.availability_types import InsufficientStock
from apps.inventory.models import InventoryProduct


def _atomic(name):
    if not connection.in_atomic_block:
        raise RuntimeError(f"{name} must be called inside transaction.atomic().")


def _move(product, quantity, *, to_reserved):
    if to_reserved and product.available_quantity < quantity:
        raise InsufficientStock(
            f"Insufficient stock for product {product.pk}: requested {quantity}, "
            f"available {product.available_quantity}.")
    if not to_reserved and product.reserved_quantity < quantity:
        raise InsufficientStock(
            f"Insufficient reserved stock for product {product.pk}: releasing {quantity}, "
            f"reserved {product.reserved_quantity}.")
    sign = 1 if to_reserved else -1
    product.available_quantity -= sign * quantity
    product.reserved_quantity += sign * quantity
    save_stock_change(product, update_fields=["available_quantity", "reserved_quantity", "updated_at"])
    return product


def release_request_reservation(request):
    """Return an accepted request's reserved units to available (cancel or expiry)."""
    _atomic("release_request_reservation")
    quantities = {}
    for item in request.items.order_by("product_id"):
        if item.accepted_quantity > 0:
            quantities[item.product_id] = quantities.get(item.product_id, 0) + item.accepted_quantity
    products = InventoryProduct.objects.select_for_update().filter(pk__in=quantities).order_by("pk")
    for product in products:
        _move(product, quantities[product.pk], to_reserved=False)
    return quantities


def hold_for_waitlist(product_id, quantity):
    """Hold ``quantity`` free units for a waitlist offer (available -> reserved)."""
    _atomic("hold_for_waitlist")
    from apps.inventory.availability_requests import assert_individual_assets_available
    product = InventoryProduct.objects.select_for_update().get(pk=product_id)
    assert_individual_assets_available(product, int(quantity))
    return _move(product, int(quantity), to_reserved=True)


def release_waitlist_hold(product_id, quantity):
    """Give a lapsed, left or claimed offer's held units back (reserved -> available)."""
    _atomic("release_waitlist_hold")
    product = InventoryProduct.objects.select_for_update().get(pk=product_id)
    if quantity <= 0:
        return product
    return _move(product, int(quantity), to_reserved=False)
