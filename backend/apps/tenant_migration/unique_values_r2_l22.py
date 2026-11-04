"""Deployment-global uniqueness for lane L22's rows (the per-space shop).

Product slugs, SKUs and pickup codes are unique per space and travel with it (their space is
remapped, so they cannot collide with another space's). One-per-parent rows follow their
remapped parent. A guest's status-link secret is bearer material and is minted fresh.
"""

from .unique_values_policy import REMAP, _policy

_FOLLOW = "Unique per remapped parent row; follows the imported parent."
_SPACE = "Unique within one space; the space is remapped on import, so it cannot collide."

RULES = {
    ("shop.ShopSettings", "field:makerspace"): _policy(REMAP, _FOLLOW),
    ("shop.ShopProduct", "shop_product_unique_slug"): _policy(REMAP, _SPACE),
    ("shop.ShopVariant", "shop_variant_unique_sku"): _policy(REMAP, _SPACE),
    ("shop.ShopOrder", "shop_order_unique_pickup_code"): _policy(REMAP, _SPACE),
    ("shop.ShopKitComponent", "shop_kit_component_unique"): _policy(REMAP, _FOLLOW),
    ("shop.ShopCheckoutHold", "shop_hold_one_per_variant"): _policy(REMAP, _FOLLOW),
    ("shop.ShopCashSession", "shop_cash_session_one_open"): _policy(REMAP, _SPACE),
}
