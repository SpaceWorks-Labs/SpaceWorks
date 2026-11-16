"""Decision 242 / SH3: the Shop Manager's product-by-month sales table and stock-value table.

`shop-product-sales`: units and sales per product line per makerspace-local month, from the same paid orders
as `shop-sales` (so the two always reconcile). `shop-stock-value`: on-hand units and shelf value (price x
on-hand) per variant, own stock only (an inventory-linked variant draws on the inventory item, never counted
here). Both are the shop's own money for `manage_shop`; no view_finance and no identity column.
"""

from collections import defaultdict
from decimal import Decimal

from apps.makerspaces.local_time import to_local
from apps.operations.report_types import ReportResult
from apps.operations.reports_finance_sources import finance_window
from apps.operations.reports_shop import _spaces, paid_orders

SALES_FIELDS = ("month", "product", "currency", "units", "sales")
STOCK_FIELDS = ("product", "variant", "currency", "on_hand", "held", "unit_price", "stock_value")
ZERO = Decimal("0.00")


def build_shop_product_sales(makerspace_id, *, limit=None, date_range=None, actor=None):
    records = []
    for space in _spaces(makerspace_id):
        groups = defaultdict(lambda: [0, ZERO])
        for order in paid_orders(space, finance_window(space, date_range)):
            month = to_local(space, order.paid_at).strftime("%Y-%m")
            for line in order.lines.all():
                group = groups[(month, line.label, order.currency)]
                group[0] += line.quantity
                group[1] += line.line_total
        records += [{"month": month, "product": label, "currency": currency, "units": units, "sales": sales}
                    for (month, label, currency), (units, sales) in sorted(groups.items())]
    return ReportResult(SALES_FIELDS, records if limit is None else records[:limit], {
        "definition": "Units sold and what was charged for each shop item in each makerspace-local month, from the "
                      "orders paid in that month.",
        "columns": "sales = line total charged (tax included).",
        "calendar": "makerspace local time",
    })


def build_shop_stock_value(makerspace_id, *, limit=None, date_range=None, actor=None):
    from apps.payments.models import MakerspacePaymentSettings
    from apps.shop.models import ShopVariant

    records = []
    for space in _spaces(makerspace_id):
        currency = MakerspacePaymentSettings.for_makerspace(space).default_currency
        variants = ShopVariant.objects.filter(product__makerspace=space, product__archived_at__isnull=True,
                                              linked_product__isnull=True).select_related("product").order_by(
            "product__name", "pk")
        for variant in variants:
            records.append({"product": variant.product.name, "variant": getattr(variant, "name", "") or "",
                            "currency": currency, "on_hand": variant.on_hand, "held": variant.held,
                            "unit_price": variant.price, "stock_value": variant.price * variant.on_hand})
    return ReportResult(STOCK_FIELDS, records if limit is None else records[:limit], {
        "definition": "Own shelf stock per shop variant (inventory-linked variants are excluded) valued at the selling "
                      "price today.",
        "columns": "stock_value = unit_price x on_hand; held = units kept for checkouts in progress.",
        "calendar": "makerspace local time",
    })
