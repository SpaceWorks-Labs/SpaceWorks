"""Release-2 lane L22 (the per-space shop): literal export classification.

Exported with the space: shop settings, products, variants, kit parts, stock movements,
checkout holds, orders with their lines and returns, and front-desk cash sessions. A
guest buyer's name and email are scoped PII (encrypted at rest, `encryption/registry_r2_l22`).
Every table carries a dataset predicate: the ones that reach their space only through a
parent (order lines) name that parent's space (L8: an unpredicated table is not policed).

Omitted, deliberately: an order's `status_secret`, the bearer secret behind a guest's
signed status link. A moved space mints a fresh one; the buyer can ask for a new link.
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "shop.ShopSettings": "id makerspace online_hold_minutes desk_hold_hours returns_window_days first_reminder_days "
                         "second_reminder_days uncollected_cancel_days policy_text pickup_note updated_by updated_at",
    "shop.ShopProduct": "id makerspace kind name slug description image_key category is_public is_active sort_order "
                        "unit max_per_order members_only show_exact_stock tax_rate_bps hsn_code bundle_mode "
                        "archived_at created_by created_at updated_at",
    "shop.ShopVariant": "id makerspace product name options sku price on_hand held reorder_point linked_product "
                        "is_active sort_order archived_at created_at",
    "shop.ShopKitComponent": "id makerspace kit component quantity",
    "shop.ShopStockMovement": "id makerspace variant kind quantity balance_after reason order actor created_at",
    "shop.ShopCheckoutHold": "id makerspace order variant quantity expires_at released_at release_reason created_at",
    "shop.ShopOrder": "id makerspace channel status buyer guest_name guest_email pickup_at pickup_event pickup_code "
                      "currency subtotal discount_total total tax_total amount_due pricing_snapshot digest "
                      "status_secret cash_session created_by created_at expires_at paid_at ready_at collected_at "
                      "collected_by closed_at close_reason reminders_sent",
    "shop.ShopOrderLine": "id order variant label sku quantity unit_amount discount_amount line_total tax_rate_bps "
                          "hsn_code taxable_amount tax_amount",
    "shop.ShopOrderReturn": "id makerspace order line quantity disposition amount refund_case reason created_by "
                            "created_at",
    "shop.ShopCashSession": "id makerspace status currency opening_float opened_by opened_at counted_cash "
                            "expected_cash variance note closed_by closing_at confirmed_by closed_at",
}
FIELD_ADDITIONS = {"procurement.ToBuyItem": "source_shop_variant"}
ALWAYS_OMITTED = {
    ("shop.ShopOrder", "status_secret"): "Bearer secret of a guest's status link; a moved space mints a new one.",
}
NON_CREDENTIAL = {
    ("shop.ShopOrder", "digest"): "Digest of the quote a buyer was shown (price-changed check); authenticates nothing.",
    ("shop.ShopOrder", "pickup_code"): "A short handover code shown to the buyer; staff still check it at the desk "
                                       "and it opens nothing online.",
}
DATASET_SPECS = {
    "shop.ShopSettings": ("shop/settings.csv", P(("makerspace",))),
    "shop.ShopProduct": ("shop/products.csv", P(("makerspace",))),
    "shop.ShopVariant": ("shop/variants.csv", P(("makerspace",))),
    "shop.ShopKitComponent": ("shop/kit_components.csv", P(("makerspace",))),
    "shop.ShopStockMovement": ("shop/stock_movements.csv", P(("makerspace",))),
    "shop.ShopCheckoutHold": ("shop/checkout_holds.csv", P(("makerspace",))),
    "shop.ShopOrder": ("shop/orders.csv", P(("makerspace",))),
    "shop.ShopOrderLine": ("shop/order_lines.csv", P(("order", "makerspace"))),
    "shop.ShopOrderReturn": ("shop/order_returns.csv", P(("makerspace",))),
    "shop.ShopCashSession": ("shop/cash_sessions.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("shop.ShopSettings", "updated_by"),
    ("shop.ShopProduct", "created_by"),
    ("shop.ShopStockMovement", "actor"),
    ("shop.ShopOrder", "buyer"),
    ("shop.ShopOrder", "created_by"),
    ("shop.ShopOrder", "collected_by"),
    ("shop.ShopOrderReturn", "created_by"),
    ("shop.ShopCashSession", "opened_by"),
    ("shop.ShopCashSession", "closed_by"),
    ("shop.ShopCashSession", "confirmed_by"),
})
# The frozen order quote: component, item names and variant ids, prices and the digest only.
JSON_FIELDS = frozenset({("shop.ShopOrder", "pricing_snapshot")})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in FIELD_ADDITIONS.items():
        fields[label] += " " + extra
    return fields
