"""Lane L6 rows in the capture-bound money fingerprint.

An order's status decides whether its seats are owed money, a live hold can still turn
into a paid order, and an order due opens a refund case. Orders, holds and dues (series
pass dues included) therefore participate, as do venue fees. Each key is omitted when
empty, so a space that never sold an order keeps its existing fingerprint.
"""


def _rows(model, using, values, **lookup):
    from apps.backup.capture_managers import every_row
    return [{key: str(value) for key, value in row.items()}
            for row in every_row(model).using(using).filter(**lookup).order_by("pk").values(*values)]


def l6_money_rows(makerspace_id, using="default"):
    from django.apps import apps

    get = apps.get_model
    parts = {
        "event_orders": _rows(get("events.EventOrder"), using, ("id", "status", "total", "currency", "paid_at"),
                              makerspace_id=makerspace_id),
        "event_checkout_holds": _rows(get("events.EventCheckoutHold"), using,
                                      ("id", "order_id", "seats", "expires_at", "released_at"),
                                      makerspace_id=makerspace_id),
        "event_order_dues": _rows(get("events.EventOrderDue"), using,
                                  ("id", "order_id", "kind", "amount", "refund_case_id"),
                                  makerspace_id=makerspace_id),
        "event_venue_fees": _rows(get("events.EventVenueFee"), using, ("id", "status", "mode", "amount"),
                                  makerspace_id=makerspace_id),
    }
    return {key: rows for key, rows in parts.items() if rows}
