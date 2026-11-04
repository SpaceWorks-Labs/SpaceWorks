"""Shop lines (lane L22): one `item` line per variant, priced at the variant's own price.

`params["lines"]` is a list of `(ShopVariant, quantity)`. The variant's price IS its item
price (there is no space rate card for shop goods); a member discount for the `shop`
domain applies on top through `best_discount` like every other domain (Q-S6). Shop prices
are entered tax-inclusive when `shop.tax` is on; the quote stays the price as entered.
"""

from apps.payments.pricing.components import component
from apps.payments.pricing.quotes import line


def label_for(variant):
    product = variant.product
    if variant.name and variant.name != "Standard":
        return f"{product.name} ({variant.name})"[:240]
    return product.name[:240]


def shop_lines(card, lines):
    item = component("shop", "item")
    return [line(item, currency=card.currency, quantity=quantity, unit_amount=variant.price, rate_source="item",
                 target={"type": "shop_variant", "id": variant.pk, "label": label_for(variant)},
                 detail={"product_id": variant.product_id, "sku": variant.sku})
            for variant, quantity in lines]
