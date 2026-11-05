"""Release-2 lane L22: the per-space shop (#128 C-7, #129, #135, #137).

The shop is its own top-level module `shop` (an owner exception to #97, #135 Q-S1), off by
default. EVERY shop feature is optional with its own switch (#135); the answers below are
the behaviour when that switch is on. Turning one off keeps its data (#95, #128 C-8).

* `shop.online` -- the public shop page `/m/<slug>/shop` and online orders for pickup.
* `shop.guest_checkout` -- buyers without an account: name, email and an emailed code (Q-S5).
* `shop.holds` -- an online checkout holds its stock for 15 minutes and a pay-at-desk order
  for 48 hours (Q-S4). Off: stock is taken only when payment lands.
* `shop.member_prices` -- the space's automatic member discounts apply to shop items, and
  a product may be members-only (Q-S6).
* `shop.tax` -- a tax class per product (rate and HSN code), prices tax-inclusive, place of
  supply the space's state (Q-S2). Needs `billing.tax`.
* `shop.returns` -- staff take items back within the returns window, restocked or written
  off, with a refund case for the money (Q-S7).
* `shop.cash_up` -- front-desk cash sessions: float, counted cash, variance (Q-S8, Q-S19).
* `shop.event_pickup` -- collect an online order at one of the space's events (#135 Q-S3).
* `shop.order_limits` -- an optional per-order quantity limit per product (Q-S16).
* `shop.public_stock` -- In stock / Low / Sold out on the public page, exact counts only
  for products that opt in (Q-S14). Off: only "Sold out".
* `shop.receipts` -- the receipt or tax invoice on screen, by email and printable at 80 mm
  and A4 (Q-S15). The ledger's own documents are issued either way.
* `shop.reorder` -- at a variant's reorder point, a To-Buy draft (with `inventory.tobuy`)
  or else a staff notice (Q-S13).
* `shop.bundles` -- a kit can take each component's stock at sale (Q-S12).
* `shop.consumable_link` -- a variant may draw on an inventory consumable (Q-S11).

Money: `charges.shop` records every sale (standalone, default on, like `charges.enabled`,
so turning the shop on never sells unrecorded); `payments.shop` adds the online card/UPI
rail and needs the `payments` module. With it off, online orders are "pay at the desk".
"""


def definitions(feature):
    shop = "shop"
    return (
        feature("shop.online", shop, "Online shop",
                "A public shop page where buyers order for pickup at the space."),
        feature("shop.guest_checkout", shop, "Guest checkout",
                "Buyers without an account order with their name, email and an emailed code.",
                requires_features=("shop.online",)),
        feature("shop.holds", shop, "Stock holds at checkout",
                "Stock is kept aside for 15 minutes while a buyer pays online, and for 48 hours for a "
                "pay-at-desk order.", default_enabled=True),
        feature("shop.member_prices", shop, "Member prices",
                "The space's automatic member discounts apply to shop items, and products can be "
                "members-only."),
        feature("shop.tax", shop, "Shop tax classes",
                "Each product carries its own tax rate and HSN code; prices include tax.",
                requires_features=("billing.tax",)),
        feature("shop.returns", shop, "Returns and refunds",
                "Staff take items back within the returns window, back to stock or written off, with "
                "a refund case for the money."),
        feature("shop.cash_up", shop, "Cash-up",
                "Front-desk cash sessions: opening float, counted cash and the variance."),
        feature("shop.event_pickup", shop, "Pickup at events",
                "Buyers may collect an online order at one of the space's events.",
                requires_modules=("events",)),
        feature("shop.order_limits", shop, "Per-order limits",
                "A product can limit how many a buyer takes in one order."),
        feature("shop.public_stock", shop, "Stock on the shop page",
                "In stock, Low and Sold out labels on the public page; exact counts only for products "
                "that opt in.", default_enabled=True, requires_features=("shop.online",)),
        feature("shop.receipts", shop, "Shop receipts",
                "The receipt or tax invoice on screen, by email and printable at 80 mm and A4.",
                default_enabled=True),
        feature("shop.reorder", shop, "Low-stock reorder",
                "At a variant's reorder point, a To-Buy draft (with To-Buy on) or a staff notice."),
        feature("shop.bundles", shop, "Kit bundles",
                "A kit can take each of its components' stock when it is sold."),
        feature("shop.consumable_link", shop, "Sell inventory consumables",
                "A product can draw on an inventory consumable, so workshop use and sales share one "
                "count. Lendable tools are never sold."),
        feature("charges.shop", None, "Track shop sales",
                "Record every shop sale as a charge in the finance ledger, whether or not online "
                "payment is configured.", default_enabled=True),
        feature("payments.shop", shop, "Online shop payments",
                "Take card and UPI payment online for shop orders; without it, online orders are paid "
                "at the desk.", requires_modules=("payments",)),
    )
