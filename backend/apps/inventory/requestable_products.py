"""The public-safe returnable predicate shared by request intake and pickers."""
from apps.inventory.models import InventoryProduct


def requestable_products(makerspace, *, event_context=False):
    """Event-only products (decision 221b) are requestable only inside an event context."""
    rows = InventoryProduct.objects.filter(
        makerspace=makerspace, is_public=True, is_archived=False, is_consumable=False,
    )
    return rows if event_context else rows.filter(event_only=False)
