"""Tinkerspace shop (release 2 L22, #134 walkthrough), through the real services.

Turns the shop on with its online page, holds, receipts, cash-up, returns and low-stock
reorder, and seeds a small catalogue: a PLA spool (consumable), an Arduino starter kit
(kit) and a Tinkerspace T-shirt with sizes (merch). The Shop Manager restocks them, opens
the cash drawer and sells a T-shirt for cash at the desk; a member places an online
pay-at-desk order that waits on the pickup shelf.
"""

from decimal import Decimal

from apps.accounts.models import User

FEATURES = ("shop.online", "shop.holds", "shop.receipts", "shop.cash_up", "shop.returns", "shop.reorder",
            "shop.public_stock", "shop.order_limits", "charges.enabled", "charges.shop")
PRODUCTS = (
    {"kind": "consumable", "name": "PLA filament spool, 1 kg", "category": "Filament", "unit": "spool",
     "variants": [{"name": "Black", "sku": "PLA-BLK", "price": Decimal("1200.00"), "reorder_point": 3},
                  {"name": "White", "sku": "PLA-WHT", "price": Decimal("1200.00"), "reorder_point": 3}]},
    {"kind": "kit", "name": "Arduino starter kit", "category": "Kits", "max_per_order": 2,
     "variants": [{"name": "Standard", "sku": "KIT-ARD", "price": Decimal("2499.00"), "reorder_point": 2}]},
    {"kind": "merch", "name": "Tinkerspace T-shirt", "category": "Merch", "show_exact_stock": True,
     "variants": [{"name": size, "options": {"size": size}, "sku": f"TEE-{size}", "price": Decimal("599.00")}
                  for size in ("S", "M", "L")]},
)


def seed_shop(space, manager, member):
    from apps.shop import services_cash, services_catalogue, services_pos
    from apps.shop.checkout import Buyer, place_online_order

    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"shop"})
    space.enabled_features = sorted(set(space.enabled_features or []) | set(FEATURES))
    space.save(update_fields=["enabled_modules", "enabled_features"])
    space.refresh_from_db()
    seller = User.objects.filter(username="tinker_shop").first() or manager
    products = [services_catalogue.save_product(space, dict(row), actor=seller) for row in PRODUCTS]
    for product in products:
        for variant in product.variants.all():
            services_catalogue.move_stock(variant, actor=seller, kind="restock", quantity=12,
                                          reason="Opening stock")
    shirt = products[2].variants.get(sku="TEE-M")
    services_cash.open_cash(space, actor=seller, opening_float=Decimal("2000.00"))
    services_pos.pos_sale(space, actor=seller, lines=[{"variant_id": shirt.pk, "quantity": 1}], method="cash")
    spool = products[0].variants.get(sku="PLA-BLK")
    place_online_order(space, Buyer(account=member, name=member.get_full_name() or member.username,
                                    email=member.email or "", actor=member),
                       {"lines": [{"variant_id": spool.pk, "quantity": 1}], "pickup_at": "space"})
    return products
