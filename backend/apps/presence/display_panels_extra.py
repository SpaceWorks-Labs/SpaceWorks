"""Inventory highlights and sponsor logo wall for a paired display (decision 325a).

Both reuse the public site's own rules rather than restating them: the highlights read exactly the rows
the public catalogue lists (public, not archived, not a consumable) through the same availability
projection, so `public_availability_mode` and `show_public_count` decide what a number looks like, and no
location, box, QR code or hidden count is ever selected. The wall is the space's public sponsor wall.
"""
from apps.inventory import public_image_storage
from apps.inventory.models import InventoryProduct
from apps.inventory.public_availability import get_public_availability
from apps.makerspaces.public_page_derived import public_catalogue_open

MAX_HIGHLIGHTS = 8
MAX_SPONSORS = 24


def inventory_highlights(space):
    """Most-lent public items with their public availability, or None while the catalogue is closed."""
    if not public_catalogue_open(space):
        return None
    rows = InventoryProduct.objects.filter(
        makerspace=space, is_public=True, is_archived=False, is_consumable=False,
    ).select_related("category").order_by("-issued_quantity", "name", "pk")[:MAX_HIGHLIGHTS]
    items = [{"name": row.name, "category": row.category.name if row.category_id else "",
              "image_url": public_image_storage.public_url(row.image_key) or None,
              "availability": get_public_availability(row)} for row in rows]
    return {"items": items} if items else None


def sponsors_wall(space):
    """Name, tier and logo of the sponsors on the public wall, or None while the wall is off or empty."""
    from apps.payments.donations.wall import wall
    cards = wall(space)
    if not cards:
        return None
    return {"sponsors": [{"name": c["name"], "tier": c["tier"], "logo_url": c["logo_url"] or None}
                         for c in cards[:MAX_SPONSORS]]}
