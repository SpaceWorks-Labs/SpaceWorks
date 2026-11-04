"""Audit metadata IDs written by release-2 lane L22 (the per-space shop)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP


def _remap(model, *edges):
    return {edge: AuditReference(R, model) for edge in edges}


_ORDER = ("order_placed", "order_paid", "order_paid_at_desk", "order_ready", "order_collected", "order_cancelled",
          "order_unfulfilled", "pos_sale", "refund_requested", "stock_returned", "stock_written_off")
_VARIANT = ("variant_created", "variant_updated", "variant_archived", "stock_restocked", "stock_adjusted",
            "stock_returned", "stock_written_off")

EDGES = {
    **_remap("shop.ShopOrder", *((f"shop.{action}", "order_id") for action in _ORDER)),
    **_remap("shop.ShopProduct", *((f"shop.{action}", "product_id") for action in (
        "product_created", "product_updated", "product_archived", "product_image_set", "product_image_cleared",
        "variant_created", "variant_updated", "variant_archived"))),
    **_remap("shop.ShopVariant", *((f"shop.{action}", "variant_id") for action in _VARIANT),
             ("shop.order_unfulfilled", "variant_id"), ("procurement.auto_tobuy_created", "shop_variant_id")),
    **_remap("shop.ShopOrderLine", ("shop.stock_returned", "line_id"), ("shop.stock_written_off", "line_id")),
    **_remap("shop.ShopCashSession", *((f"shop.{action}", "session_id") for action in (
        "cash_session_opened", "cash_session_close_proposed", "cash_session_closed")),
             ("shop.pos_sale", "cash_session_id"), ("shop.order_paid_at_desk", "cash_session_id")),
    **_remap("payments.RefundCase", ("shop.refund_requested", "case_id"), ("shop.order_unfulfilled", "case_id"),
             ("shop.order_cancelled", "case_id")),
    **_remap("procurement.ToBuyItem", ("shop.stock_restocked", "to_buy_item_id")),
}
