"""Shop stock math (release 2 L22): the ONLY place a shop count changes.

The Inventory Availability Module owns every quantity (CLAUDE.md Hard Rule), the shop's
included. A variant either keeps its own stock (`on_hand`, with `held` kept aside for
checkouts) or draws on one inventory item consumable (Q-S11), whose available units this
module changes through `adjust_quantities`, so workshop use and sales stay one count. A
bundle-mode kit (Q-S12, `shop.bundles`) sells its components' stock instead of its own.

Rules: stock never goes below zero; holds and sales lock the variant rows (in primary-key
order, then the inventory rows), and every change writes an append-only
`ShopStockMovement` with its reason and actor.
"""

from collections import defaultdict

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.inventory.availability_types import InsufficientStock


class OutOfStock(InsufficientStock):
    def __init__(self, variant_id, available=0):
        super().__init__("Not enough stock.")
        self.variant_id = variant_id
        self.available = max(int(available), 0)


def _models():
    from apps.shop.models import ShopCheckoutHold, ShopStockMovement, ShopVariant
    return ShopVariant, ShopCheckoutHold, ShopStockMovement


def stock_units(variant, quantity, *, bundles=False):
    """[(stock variant, units)] one sale of `quantity` takes; a bundle kit names its parts."""
    if bundles and variant.product.bundle_mode:
        parts = list(variant.product.components.select_related("component"))
        if parts:
            return [(part.component, part.quantity * quantity) for part in parts]
    return [(variant, quantity)]


def _merge(pairs):
    totals = defaultdict(int)
    for variant, units in pairs:
        totals[variant.pk] += units
    return totals


def _locked_variants(ids):
    ShopVariant = _models()[0]
    return {row.pk: row for row in ShopVariant.objects.select_for_update().filter(pk__in=ids).order_by("pk")}


def _linked_held(product_id):
    ShopVariant = _models()[0]
    return ShopVariant.objects.filter(linked_product_id=product_id).aggregate(total=Sum("held"))["total"] or 0


def available(variant):
    """Units of THIS stock variant a buyer may take now (no kit expansion)."""
    if variant.linked_product_id:
        from apps.inventory.models import InventoryProduct
        product = InventoryProduct.objects.filter(pk=variant.linked_product_id).values_list(
            "available_quantity", flat=True).first() or 0
        return max(product - _linked_held(variant.linked_product_id), 0)
    return max(variant.on_hand - variant.held, 0)


def sellable(variant, *, bundles=False):
    """How many of `variant` can be sold now, a bundle kit limited by its scarcest part."""
    units = stock_units(variant, 1, bundles=bundles)
    return min((available(part) // need for part, need in units), default=0)


def _record(variant, kind, quantity, balance, *, actor, reason="", order=None):
    _models()[2].objects.create(makerspace_id=variant.makerspace_id, variant=variant, kind=kind, quantity=quantity,
                                balance_after=balance, reason=(reason or "")[:200], order=order, actor=actor)


def _balance(variant):
    if variant.linked_product_id:
        from apps.inventory.models import InventoryProduct
        return InventoryProduct.objects.values_list("available_quantity", flat=True).get(pk=variant.linked_product_id)
    return variant.on_hand


@transaction.atomic
def hold_for_checkout(order, pairs, *, expires_at):
    """Keep `pairs` [(stock variant, units)] aside for `order` until `expires_at`."""
    _, ShopCheckoutHold, _ = _models()
    totals = _merge(pairs)
    locked = _locked_variants(totals)
    for pk in sorted(totals):
        variant, units = locked[pk], totals[pk]
        if available(variant) < units:
            raise OutOfStock(pk, available(variant))
        variant.held += units
        variant.save(update_fields=["held"])
        ShopCheckoutHold.objects.create(makerspace_id=order.makerspace_id, order=order, variant=variant,
                                        quantity=units, expires_at=expires_at)


@transaction.atomic
def release_hold(order, reason):
    """Give back every live hold of `order`. Returns how many hold rows were released."""
    _, ShopCheckoutHold, _ = _models()
    holds = list(ShopCheckoutHold.objects.select_for_update().filter(order=order, released_at__isnull=True))
    locked = _locked_variants({hold.variant_id for hold in holds})
    for hold in holds:
        variant = locked[hold.variant_id]
        variant.held = max(variant.held - hold.quantity, 0)
        variant.save(update_fields=["held"])
        hold.released_at, hold.release_reason = timezone.now(), reason
        hold.save(update_fields=["released_at", "release_reason"])
    return len(holds)


@transaction.atomic
def sell(order, pairs, *, actor, reason="Sold"):
    """Take `pairs` out of stock for `order`, spending its live holds first. All or nothing."""
    from apps.inventory.availability_quantities import adjust_quantities
    _, ShopCheckoutHold, ShopStockMovement = _models()
    totals = _merge(pairs)
    holds = {hold.variant_id: hold for hold in ShopCheckoutHold.objects.select_for_update().filter(
        order=order, released_at__isnull=True)}
    locked = _locked_variants(set(totals) | set(holds))
    for pk in sorted(totals):
        variant, units, hold = locked[pk], totals[pk], holds.get(pk)
        kept = min(hold.quantity, units) if hold else 0
        before, free = variant.on_hand, available(variant)  # free stock beyond every live hold
        if free < units - kept:
            raise OutOfStock(pk, free + kept)
        if hold:
            variant.held = max(variant.held - hold.quantity, 0)
        if variant.linked_product_id:
            variant.save(update_fields=["held"])
            adjust_quantities(variant.linked_product, delta_available=-units, delta_damaged=0, delta_lost=0,
                              reason=f"Shop order #{order.pk}", actor=actor)
        else:
            variant.on_hand -= units
            variant.save(update_fields=["on_hand", "held"])
        _record(variant, ShopStockMovement.Kind.SALE, -units, _balance(variant), actor=actor, reason=reason,
                order=order)
        if hold:
            hold.released_at, hold.release_reason = timezone.now(), ShopCheckoutHold.Reason.SOLD
            hold.save(update_fields=["released_at", "release_reason"])
        _after_drop(variant, before)
    for pk, hold in holds.items():  # a hold for a variant no longer in the order goes back
        if pk not in totals:
            locked[pk].held = max(locked[pk].held - hold.quantity, 0)
            locked[pk].save(update_fields=["held"])
            hold.released_at, hold.release_reason = timezone.now(), ShopCheckoutHold.Reason.CANCELLED
            hold.save(update_fields=["released_at", "release_reason"])


@transaction.atomic
def return_to_stock(order, pairs, *, actor, write_off=False, reason=""):
    """Returned units go back on the shelf, or are written off (recorded, count unchanged)."""
    from apps.inventory.availability_quantities import adjust_quantities
    ShopStockMovement = _models()[2]
    totals = _merge(pairs)
    locked = _locked_variants(totals)
    for pk in sorted(totals):
        variant, units = locked[pk], totals[pk]
        if write_off:
            _record(variant, ShopStockMovement.Kind.WRITTEN_OFF, 0, _balance(variant), actor=actor, reason=reason,
                    order=order)
            continue
        if variant.linked_product_id:
            adjust_quantities(variant.linked_product, delta_available=units, delta_damaged=0, delta_lost=0,
                              reason=f"Shop return, order #{order.pk}", actor=actor)
        else:
            variant.on_hand += units
            variant.save(update_fields=["on_hand"])
        _record(variant, ShopStockMovement.Kind.RETURNED, units, _balance(variant), actor=actor, reason=reason,
                order=order)


@transaction.atomic
def restock(variant, quantity, *, actor, reason=""):
    """Units arrived (a purchase, a To-Buy row marked bought). Own stock only."""
    ShopStockMovement = _models()[2]
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
        raise InsufficientStock("Restock quantity must be a positive whole number.")
    locked = _locked_variants([variant.pk])[variant.pk]
    if locked.linked_product_id:
        raise InsufficientStock("This item draws on an inventory consumable; restock it in the inventory.")
    locked.on_hand += quantity
    locked.save(update_fields=["on_hand"])
    _record(locked, ShopStockMovement.Kind.RESTOCK, quantity, locked.on_hand, actor=actor, reason=reason)
    return locked


@transaction.atomic
def adjust(variant, delta, *, kind, actor, reason):
    """A count correction, damage or internal use. Never below zero nor below live holds."""
    ShopStockMovement = _models()[2]
    if kind not in ShopStockMovement.ADJUST_KINDS or not reason.strip():
        raise InsufficientStock("An adjustment needs a kind and a reason.")
    locked = _locked_variants([variant.pk])[variant.pk]
    if locked.linked_product_id:
        raise InsufficientStock("This item draws on an inventory consumable; adjust it in the inventory.")
    if locked.on_hand + delta < locked.held or locked.on_hand + delta < 0:
        raise OutOfStock(locked.pk, locked.on_hand - locked.held)
    before = locked.on_hand
    locked.on_hand += delta
    locked.save(update_fields=["on_hand"])
    _record(locked, kind, delta, locked.on_hand, actor=actor, reason=reason)
    if delta < 0:
        _after_drop(locked, before)
    return locked


def _after_drop(variant, before):
    """Q-S13: crossing down to the reorder point -> a To-Buy draft or a staff notice (after commit).

    Own stock only: a variant drawing on an inventory consumable follows that item's own
    reorder point and auto-draft (`availability_stock`)."""
    point = variant.reorder_point
    if variant.linked_product_id or point <= 0 or not before > point >= variant.on_hand:
        return
    variant_id = variant.pk

    def fell():
        from apps.shop.reorder import stock_fell
        stock_fell(variant_id)

    transaction.on_commit(fell)
