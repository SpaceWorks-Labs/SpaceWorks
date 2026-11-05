"""Deployment-global uniqueness for lane L22's rows (the per-space shop).

Slugs, SKUs and pickup codes are unique per space, so they are no deployment-global risk.
One-per-parent rows follow their remapped parent. A guest's status-link secret is bearer
material and is minted fresh.
"""

from .unique_values_policy import FRESH, REMAP, _policy

_FOLLOW = "Unique per remapped parent row; follows the imported parent."

RULES = {
    ("shop.ShopKitComponent", "shop_kit_component_unique"): _policy(REMAP, _FOLLOW),
    ("shop.ShopCheckoutHold", "shop_hold_one_per_variant"): _policy(REMAP, _FOLLOW),
    ("shop.ShopOrder", "field:status_secret"): _policy(FRESH, "A guest status-link secret is bearer material; "
                                                              "the target mints a fresh one."),
}
