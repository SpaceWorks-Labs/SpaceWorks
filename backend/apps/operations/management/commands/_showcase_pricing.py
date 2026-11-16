"""Tinkerspace pricing: a paid lending rate card, one Free item and a plan discount (lane L15).

Written through the same services the Pricing screens use, so the audit trail, the
settings-authority record and the price preview all have something to show. Seeded
after the loans, so the seeded requests keep their release-1 charges.
"""

from decimal import Decimal

from apps.inventory.models import InventoryProduct
from apps.payments.models import PriceOverride
from apps.payments.pricing import admin_services, discount_services


def seed_pricing(space, manager, plan):
    admin_services.set_default(manager, space, "loans", mode="paid", lines=[
        {"component": "rental_per_day", "amount": Decimal("1.00"), "cap": Decimal("5.00")},
        {"component": "damage", "amount": Decimal("10.00")},
    ])
    free_item = InventoryProduct.objects.filter(makerspace=space, is_public=True, is_archived=False).order_by("pk").first()
    if free_item is not None:
        admin_services.set_override(manager, space, PriceOverride.TargetType.INVENTORY_PRODUCT, free_item.pk,
                                    "rental_per_day", mode=PriceOverride.Mode.FREE)
    discount_services.create_discount(manager, space, {
        "name": "Monthly makers save 10%", "audience": "plan", "plan": plan, "percent_bps": 1000,
        "domains": ["loans", "machines", "bookings"],
    })
