"""Audit presentation for lane L22: the per-space shop (#128 C-7, #135-#137)."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P


ENTRIES = (
    P("shop.product_created", gettext_noop("Shop product created")),
    P("shop.product_updated", gettext_noop("Shop product changed")),
    P("shop.product_archived", gettext_noop("Shop product archived")),
    P("shop.product_image_set", gettext_noop("Shop product image set")),
    P("shop.product_image_cleared", gettext_noop("Shop product image removed")),
    P("shop.variant_created", gettext_noop("Shop variant created")),
    P("shop.variant_updated", gettext_noop("Shop variant changed")),
    P("shop.variant_archived", gettext_noop("Shop variant archived")),
    P("shop.stock_restocked", gettext_noop("Shop stock restocked")),
    P("shop.stock_adjusted", gettext_noop("Shop stock adjusted")),
    P("shop.stock_returned", gettext_noop("Shop items returned to stock")),
    P("shop.stock_written_off", gettext_noop("Shop items written off")),
    P("shop.order_placed", gettext_noop("Shop order placed")),
    P("shop.order_paid", gettext_noop("Shop order paid")),
    P("shop.order_paid_at_desk", gettext_noop("Shop order paid at the desk")),
    P("shop.order_ready", gettext_noop("Shop order ready for pickup")),
    P("shop.order_collected", gettext_noop("Shop order collected")),
    P("shop.order_cancelled", gettext_noop("Shop order cancelled")),
    P("shop.order_unfulfilled", gettext_noop("Paid shop order could not be filled")),
    P("shop.pos_sale", gettext_noop("Front-desk sale")),
    P("shop.refund_requested", gettext_noop("Shop refund opened")),
    P("shop.cash_session_opened", gettext_noop("Cash drawer opened")),
    P("shop.cash_session_close_proposed", gettext_noop("Cash-up waiting for a second check")),
    P("shop.cash_session_closed", gettext_noop("Cash-up closed")),
)
