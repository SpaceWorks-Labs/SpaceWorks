"""Low stock (`shop.reorder`, Q-S13): a To-Buy draft, or a staff notice.

Runs after commit, when an own-stock variant crossed down to its reorder point. With
`inventory.tobuy` on (and the procurement app shipped) it writes ONE open To-Buy draft
for the variant -- an inventory-stream row the space's purchasing desk buys; marking it
bought restocks the variant through the availability module and records the spending in
the ledger (L12's bought flow, #94). Otherwise the shop staff get a low-stock notice. A
failure here never touches the sale that triggered it.
"""

import logging

from django.db import transaction

from apps.audit import services as audit

logger = logging.getLogger(__name__)


def _draft(space, variant):
    from apps.makerspaces.folded_capabilities import INVENTORY_TOBUY, capability_on
    from apps.procurement.auto_drafts import OPEN, _announce
    from apps.procurement.models import ToBuyItem
    from apps.separability.registry import runtime_active

    if not runtime_active("procurement") or not capability_on(space, INVENTORY_TOBUY):
        return None
    if ToBuyItem.objects.filter(status__in=OPEN, moved_to_inventory_at__isnull=True,
                                source_shop_variant=variant).exists():
        return False
    from apps.payments.pricing.build_shop import label_for
    item = ToBuyItem.objects.create(
        makerspace=space, kind=ToBuyItem.Kind.HARDWARE, status=ToBuyItem.Status.REQUESTED,
        name=f"Restock (shop): {label_for(variant)}"[:200], quantity=max(variant.reorder_point, 1),
        source_shop_variant=variant)
    audit.record(None, "procurement.auto_tobuy_created", makerspace=space, target=item, meta={
        "to_buy_item_id": item.pk, "shop_variant_id": variant.pk})
    _announce(item)
    return item


def stock_fell(variant_id):
    from apps.makerspaces.platform import feature_enabled

    from .models import ShopVariant
    from .notices import staff_notice

    try:
        with transaction.atomic():
            variant = ShopVariant.objects.select_related("makerspace", "product").get(pk=variant_id)
            space = variant.makerspace
            if not feature_enabled(space, "shop.reorder") or variant.on_hand > variant.reorder_point:
                return None
            made = _draft(space, variant)
            if made is None:
                staff_notice(space, variant, "shop_low_stock",
                             text=f"{variant.product.name} is down to {variant.on_hand} in the shop.")
            return made
    except Exception as exc:  # noqa: BLE001 - never fails the stock change
        logger.warning("shop_reorder_failed", extra={"variant_id": variant_id, "failure_type": type(exc).__name__})
        return None
