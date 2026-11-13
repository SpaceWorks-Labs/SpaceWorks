"""Purging the shop module's data (a superadmin /control/ action, #128 C-8).

Rows go in dependency order: orders (with their lines, returns and holds), stock history,
kit parts, event offers, variants, products, cash sessions and settings; product images are released
after commit. No shop `Payment` is deleted: a charge is core ledger and keeps its
snapshotted label and documents, so a purged shop's money stays readable and settleable.
"""


def delete(space, cursor):
    from apps.makerspaces.module_purge_collectors_single_model import PurgeResult

    from .models import (
        ShopCashSession, ShopEventOffer, ShopKitComponent, ShopOrder, ShopProduct, ShopSettings, ShopStockMovement,
        ShopVariant,
    )

    models = (ShopOrder, ShopStockMovement, ShopKitComponent, ShopEventOffer, ShopVariant, ShopProduct, ShopCashSession,
              ShopSettings)
    # Shop consumable costs key on the movements about to go (no FK). The purge runs under
    # `app.allow_immutable_delete`, which the tracking-fact trigger honours.
    cursor.execute(
        "DELETE FROM machines_consumablecostrecord WHERE makerspace_id = %s AND source_kind IN "
        "('shop_sale', 'shop_return') AND source_id IN (SELECT id FROM shop_shopstockmovement "
        "WHERE makerspace_id = %s)", [space.pk, space.pk])
    counts = {"machines.ConsumableCostRecord": cursor.rowcount} if cursor.rowcount > 0 else {}
    for model in models:
        _count, labels = model.objects.filter(makerspace=space).delete()
        for label, value in labels.items():
            counts[label] = counts.get(label, 0) + value
    from .models import ShopCheckoutHold, ShopOrderLine, ShopOrderReturn
    return PurgeResult(counts, {"machines.ConsumableCostRecord", *(model._meta.label for model in (
        *models, ShopCheckoutHold, ShopOrderLine, ShopOrderReturn))})


def public_images(space):
    from .models import ShopProduct

    return [key for key in ShopProduct.objects.filter(makerspace=space).values_list("image_key", flat=True) if key]
