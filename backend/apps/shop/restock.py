"""A To-Buy row the shop raised, marked bought: its units go on the shop shelf, exactly once.

Called by L12's bought flow (`procurement.services_bought`) inside its transaction, after
the expense is in the ledger. The quantity is the To-Buy row's; the stock moves through the
availability module (`restock`), and `moved_to_inventory_at` is the idempotency marker.
"""

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit


def restock_from_to_buy(actor, item):
    from apps.inventory.availability import restock_shop
    from apps.procurement.models import ToBuyItem

    from .models import ShopVariant

    locked = ToBuyItem.objects.select_for_update().get(pk=item.pk)
    if locked.moved_to_inventory_at is not None:
        raise ValidationError({"detail": "This item has already been put on the shelf."})
    variant = ShopVariant.objects.filter(pk=locked.source_shop_variant_id,
                                         makerspace_id=locked.makerspace_id).first()
    if variant is None or variant.linked_product_id:
        raise ValidationError({"detail": "The shop item this was raised for can no longer be restocked."})
    row = restock_shop(variant, int(locked.quantity), actor=actor, reason=f"To-Buy #{locked.pk} bought")
    locked.moved_to_inventory_at = timezone.now()
    locked.save(update_fields=["moved_to_inventory_at", "updated_at"])
    audit.record(actor, "shop.stock_restocked", makerspace=locked.makerspace, target=row, meta={
        "variant_id": row.pk, "kind": "restock", "quantity": int(locked.quantity), "on_hand": row.on_hand,
        "to_buy_item_id": locked.pk})
    return row
