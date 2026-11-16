"""Release-2 lane L22 (the per-space shop): tenant-dump field snapshot and authority.

The shop travels with its space (data_export `classification_r2_l22`): its catalogue,
stock history, orders, returns and cash-ups. The frozen order quote travels unchanged --
ids inside it are source-local history. A guest's status-link secret is replaced on the
target (`omitted_fields`); pickup codes stay unique per space (`unique_values`).
"""

FIELD_NAMES = {
    "shop.ShopSettings": "id makerspace online_hold_minutes desk_hold_hours returns_window_days first_reminder_days "
                         "second_reminder_days uncollected_cancel_days policy_text pickup_note updated_by updated_at",
    "shop.ShopProduct": "id makerspace kind name slug description image_key category is_public is_active sort_order "
                        "unit max_per_order members_only show_exact_stock tax_rate_bps hsn_code bundle_mode "
                        "archived_at created_by created_at updated_at",
    "shop.ShopVariant": "id makerspace product name options sku price on_hand held reorder_point linked_product "
                        "is_active sort_order archived_at created_at",
    "shop.ShopKitComponent": "id makerspace kit component quantity",
    "shop.ShopEventOffer": "id makerspace event variant sort_order created_at",
    "shop.ShopStockMovement": "id makerspace variant kind quantity balance_after reason order actor created_at",
    "shop.ShopCheckoutHold": "id makerspace order variant quantity expires_at released_at release_reason created_at",
    "shop.ShopOrder": "id makerspace channel status buyer guest_name guest_email pickup_at pickup_event pickup_code "
                      "currency subtotal discount_total total tax_total amount_due pricing_snapshot digest "
                      "status_secret cash_session created_by created_at expires_at paid_at ready_at collected_at "
                      "collected_by closed_at close_reason reminders_sent idempotency_key",
    "shop.ShopOrderLine": "id order variant label sku quantity unit_amount discount_amount line_total tax_rate_bps "
                          "hsn_code taxable_amount tax_amount",
    "shop.ShopOrderReturn": "id makerspace order line quantity disposition amount refund_case reason created_by "
                            "created_at",
    "shop.ShopCashSession": "id makerspace status currency opening_float opened_by opened_at counted_cash "
                            "expected_cash variance note closed_by closing_at confirmed_by closed_at",
}
FIELD_NAMES = {label: frozenset(names.split()) for label, names in FIELD_NAMES.items()}
EXTRA_FIELDS = {"procurement.ToBuyItem": frozenset({"source_shop_variant"})}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("shop.ShopOrder", "channel status currency subtotal discount_total total tax_total amount_due "
              "pricing_snapshot digest created_at expires_at paid_at ready_at collected_at closed_at close_reason "
              "reminders_sent idempotency_key", keep, "An order and its frozen quote are the buyer's money history; never recomputed."),
        *same("shop.ShopOrderLine", "label sku quantity unit_amount discount_amount line_total tax_rate_bps hsn_code "
              "taxable_amount tax_amount", keep, "The frozen price and tax split a buyer paid per line."),
        *same("shop.ShopOrderReturn", "quantity disposition amount reason created_at", keep,
              "An append-only return and the refund it opened, decided by staff through its case."),
        *same("shop.ShopStockMovement", "kind quantity balance_after reason created_at", keep,
              "Append-only stock history that explains the shelf count."),
        *same("shop.ShopCheckoutHold", "quantity expires_at released_at release_reason created_at", keep,
              "Hold history; a live hold lapses on its own clock."),
        *same("shop.ShopCashSession", "status currency opening_float opened_at counted_cash expected_cash variance "
              "note closing_at closed_at", keep, "A cash-up is the space's own cash record."),
        *same("shop.ShopVariant", "on_hand held price", keep, "The shelf count and price as the space left them."),
    )
