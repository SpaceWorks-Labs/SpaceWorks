"""Scoped-PII fields added by release-2 lane L22 (the shop): a guest buyer's name and email."""


def shop_pii_fields(field):
    return (
        field("shop.ShopOrder", "guest_name", "makerspace_id", 200, "source", "none"),
        field("shop.ShopOrder", "guest_email", "makerspace_id", 254, "source", "none"),
    )
