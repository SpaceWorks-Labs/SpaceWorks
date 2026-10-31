"""Deployment-global uniqueness for lane L15's pricing rows.

Rate cards, their lines and discounts are unique within the space (no rule). A per-item
price is unique on its item, and a revocation on the waiver it undoes: each follows its
remapped parent once.
"""

from .unique_values_policy import REMAP, _policy

RULES = {
    **{("payments.PriceOverride", f"price_override_one_per_{field}_component"): _policy(
        REMAP, "One price per component of an item; follows the imported item.")
       for field in ("product", "machine", "pool", "room")},
    ("payments.LoanFeeWaiver", "field:revokes"): _policy(
        REMAP, "One revocation per waiver; follows the imported waiver."),
}
