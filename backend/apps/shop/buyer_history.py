"""Buyer-safe child selection: the order, tenant and returned line must agree."""

from django.db.models import F, Prefetch


def buyer_return_rows():
    from .models import ShopOrderReturn

    return ShopOrderReturn.objects.filter(
        makerspace_id=F("order__makerspace_id"), line__order_id=F("order_id"),
    ).order_by("created_at", "pk")


def buyer_returns_prefetch():
    return Prefetch("returns", queryset=buyer_return_rows(), to_attr="buyer_return_history")


def returns_for_buyer(order):
    # Member lists share one filtered prefetch. Single-order guest/status/create
    # responses use the identical selector, never the unfiltered related manager.
    if hasattr(order, "buyer_return_history"):
        return order.buyer_return_history
    return buyer_return_rows().filter(order_id=order.pk)
