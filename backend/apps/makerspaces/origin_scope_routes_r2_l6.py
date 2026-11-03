"""Origin-scope table for release 2 L6's staff routes (paid ticketing v2 and venue fees).

Each names an event, a series or one of their rows; its target is that row's own space, so a
verified custom staff origin pins it like every other admin route.
"""

MODEL_LOOKUPS = {
    **{name: ("events.Event", "makerspace_id") for name in (
        "admin-event-addons", "admin-event-sales-settings", "admin-event-orders", "admin-event-refund-policy",
        "admin-event-venue-fee", "admin-event-venue-fee-charge",
    )},
    "admin-event-addon-detail": ("events.EventAddon", "makerspace_id"),
    "admin-event-order-detail": ("events.EventOrder", "makerspace_id"),
    "admin-event-series-pass-types": ("events.EventSeries", "makerspace_id"),
    "admin-event-pass-type-detail": ("events.EventPassType", "makerspace_id"),
    **{name: ("events.EventRegistration", "event__makerspace_id") for name in (
        "admin-event-registration-collect-payment", "admin-event-registration-pay-link",
    )},
}
