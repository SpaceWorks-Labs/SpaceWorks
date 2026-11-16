"""Lane L22 rows in the capture-bound money fingerprint.

An order's status decides whether money is owed or paid, a live hold can still turn into
a paid order, a return opens a refund case and a cash session holds counted cash. Each
key is omitted when empty, so a space that never ran a shop keeps its fingerprint.
"""


def _rows(model, using, values, **lookup):
    from apps.backup.capture_managers import every_row
    return [{key: str(value) for key, value in row.items()}
            for row in every_row(model).using(using).filter(**lookup).order_by("pk").values(*values)]


def l22_money_rows(makerspace_id, using="default"):
    from django.apps import apps

    get = apps.get_model
    parts = {
        "shop_orders": _rows(get("shop.ShopOrder"), using, ("id", "status", "amount_due", "currency", "paid_at"),
                             makerspace_id=makerspace_id),
        "shop_checkout_holds": _rows(get("shop.ShopCheckoutHold"), using,
                                     ("id", "order_id", "quantity", "expires_at", "released_at"),
                                     makerspace_id=makerspace_id),
        "shop_order_returns": _rows(get("shop.ShopOrderReturn"), using, ("id", "order_id", "amount", "refund_case_id"),
                                    makerspace_id=makerspace_id),
        "shop_cash_sessions": _rows(get("shop.ShopCashSession"), using,
                                    ("id", "status", "opening_float", "counted_cash", "expected_cash"),
                                    makerspace_id=makerspace_id),
    }
    return {key: rows for key, rows in parts.items() if rows}
