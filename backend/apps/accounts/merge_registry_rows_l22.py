"""Account-merge dispositions for lane L22 (the per-space shop, release 2)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_MONEY = ("Who bought and owes or paid for a shop order. Stays with the account that bought, exactly like "
          "Payment.member, which validates against it.")
_HISTORY = "Append-only attribution of a staff or member act; stays with the account that acted."
_MUTABLE = "Mutable ownership or attribution; moves to the survivor."

ROWS = (
    (K, "shop.ShopOrder", "buyer", _MONEY),
    (K, "shop.ShopOrder", "created_by collected_by", _HISTORY),
    (K, "shop.ShopOrderReturn", "created_by", _HISTORY),
    (K, "shop.ShopStockMovement", "actor", _HISTORY),
    (K, "shop.ShopCashSession", "opened_by closed_by confirmed_by", _HISTORY),
    (R, "shop.ShopProduct", "created_by", _MUTABLE),
    (R, "shop.ShopSettings", "updated_by", _MUTABLE),
)
