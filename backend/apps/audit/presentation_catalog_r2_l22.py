"""Audit presentation for lane L22: the per-space shop (#128 C-7, #135-#137)."""

from .presentation_catalog_types import P


ENTRIES = (
    P("shop.product_created", "Shop product created"),
    P("shop.product_updated", "Shop product changed"),
    P("shop.product_archived", "Shop product archived"),
    P("shop.product_image_set", "Shop product image set"),
    P("shop.product_image_cleared", "Shop product image removed"),
    P("shop.variant_created", "Shop variant created"),
    P("shop.variant_updated", "Shop variant changed"),
    P("shop.variant_archived", "Shop variant archived"),
    P("shop.stock_restocked", "Shop stock restocked"),
    P("shop.stock_adjusted", "Shop stock adjusted"),
    P("shop.stock_returned", "Shop items returned to stock"),
    P("shop.stock_written_off", "Shop items written off"),
    P("shop.order_placed", "Shop order placed"),
    P("shop.order_paid", "Shop order paid"),
    P("shop.order_paid_at_desk", "Shop order paid at the desk"),
    P("shop.order_ready", "Shop order ready for pickup"),
    P("shop.order_collected", "Shop order collected"),
    P("shop.order_cancelled", "Shop order cancelled"),
    P("shop.order_unfulfilled", "Paid shop order could not be filled"),
    P("shop.pos_sale", "Front-desk sale"),
    P("shop.refund_requested", "Shop refund opened"),
    P("shop.cash_session_opened", "Cash drawer opened"),
    P("shop.cash_session_close_proposed", "Cash-up waiting for a second check"),
    P("shop.cash_session_closed", "Cash-up closed"),
)
