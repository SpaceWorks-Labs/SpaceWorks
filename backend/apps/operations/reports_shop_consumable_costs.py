"""Shop sales of linked inventory consumables in the consumable reports (decision 216 item 11).

The shop's facts are its own `ShopStockMovement` rows, so they never overlap workshop usage
(pooled service, manual consume, non-pool consumption): one physical unit leaves stock
through exactly one of them. A sale is labelled `shop_sale`; a restock that reverses part of
it is `shop_return` with NEGATIVE quantity and cost, so totals net. Shop rows are shown only
with the `shop` module on and to a reader who holds `manage_shop` (shop money is the Shop
Manager's) or to an upstream organisation/deployment boundary (actor None).
"""

from itertools import islice

from django.db.models import Q

from apps.makerspaces.platform import module_enabled
from apps.operations.reports_common import apply_range

SALE, RETURN = "shop_sale", "shop_return"


class _Signed:
    __slots__ = ("currency", "cost_total_minor")

    def __init__(self, row):
        self.currency = row.currency
        self.cost_total_minor = -row.cost_total_minor if row.source_kind == RETURN else row.cost_total_minor


def shop_visible(space, actor):
    if not module_enabled(space, "shop"):
        return False
    if actor is None:
        return True
    from apps.accounts import rbac
    return rbac.can(actor, rbac.Action.MANAGE_SHOP, space.pk)


def _movements(space, date_range):
    from apps.shop.models import ShopStockMovement
    rows = ShopStockMovement.objects.filter(
        makerspace=space, variant__makerspace=space, variant__linked_product__isnull=False,
        kind__in=(ShopStockMovement.Kind.SALE, ShopStockMovement.Kind.RETURNED),
    ).select_related("variant__linked_product").order_by("pk")
    return apply_range(rows, "created_at", date_range)


def shop_priced_sources(space, actor, date_range=None):
    """(source, signed cost or None) in the `reports_ab_consumables.priced_sources` shape."""
    from apps.machines.models_tracking import ConsumableCostRecord
    if not shop_visible(space, actor):
        return
    movements = _movements(space, date_range).iterator()
    while batch := list(islice(movements, 200)):
        costs = {(row.source_kind, row.source_id): _Signed(row) for row in ConsumableCostRecord.objects.filter(
            makerspace=space, source_kind__in=(SALE, RETURN), source_id__in=[m.pk for m in batch]).iterator()}
        for movement in batch:
            kind = SALE if movement.kind == "sale" else RETURN
            source = (movement.created_at, kind, movement.pk, movement.variant.linked_product.name, "count",
                      -movement.quantity, "consumed_quantity")
            yield source, costs.get((kind, movement.pk))


def shop_cost_rows(space, actor, date_range=None):
    """Recorded shop costs, `recorded_at`-dated and signed, for the platform usage counts."""
    if not shop_visible(space, actor):
        return
    from apps.machines.models_tracking import ConsumableCostRecord
    from apps.shop.models import ShopStockMovement
    ids = ShopStockMovement.objects.filter(makerspace=space).values("pk")
    rows = ConsumableCostRecord.objects.filter(makerspace=space).filter(
        Q(source_kind=SALE, source_id__in=ids) | Q(source_kind=RETURN, source_id__in=ids))
    for row in apply_range(rows, "recorded_at", date_range).values(
            "recorded_at", "source_kind", "cost_total_minor", "currency").iterator():
        if row["source_kind"] == RETURN:
            row["cost_total_minor"] = -row["cost_total_minor"]
        yield row
