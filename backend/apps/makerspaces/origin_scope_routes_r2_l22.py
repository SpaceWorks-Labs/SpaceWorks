"""Origin-scope table for release 2 L22's id-only shop routes: each pins to its row's space."""

MODEL_LOOKUPS = {
    **{name: ("shop.ShopProduct", "makerspace_id") for name in ("admin-shop-product", "admin-shop-product-image")},
    **{name: ("shop.ShopVariant", "makerspace_id") for name in ("admin-shop-variant", "admin-shop-variant-stock")},
    **{name: ("shop.ShopOrder", "makerspace_id") for name in (
        "admin-shop-order", "admin-shop-order-ready", "admin-shop-order-move-pickup-to-space",
        "admin-shop-order-collect", "admin-shop-order-take-payment",
        "admin-shop-order-cancel", "admin-shop-order-returns", "admin-shop-order-receipt")},
    **{name: ("shop.ShopCashSession", "makerspace_id") for name in (
        "admin-shop-cash-session-close", "admin-shop-cash-session-confirm")},
}
