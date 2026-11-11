"""Lane L22 shop reports (#137): the shop's ledger money and its sales, for `manage_shop`.

Neither needs view_finance: the Shop Manager sees the shop's money and nothing else (Q-S10).
`finance-shop` is the finance ledger narrowed to domain `shop` (income, refunds and restock
spending by month); `shop-sales` counts orders, units, sales and refunds by month and
channel. Both are per space and never deployment-wide.
"""

from django.utils.translation import gettext_noop
from apps.accounts import rbac
from apps.operations.report_definitions_finance_l5 import LEDGER_CHART
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_de_common import chart
from apps.operations.reports_shop import FIELDS as SALES_FIELDS
from apps.operations.reports_shop_products import SALES_FIELDS as PRODUCT_FIELDS, STOCK_FIELDS
from apps.payments.reports_finance_ledger import FIELDS as LEDGER_FIELDS

SHOP_REPORT_DEFINITIONS = (
    ReportDefinition("finance-shop", "apps.payments.reports_finance_ledger.build_finance_shop", LEDGER_FIELDS,
                     ("shop",), required_action=rbac.Action.MANAGE_SHOP, title=gettext_noop("Shop money"),
                     deployment_aggregate=False, required_feature="finance.ledger", chart_hint="grouped_bar",
                     schedulable=False, chart_spec=LEDGER_CHART),
    ReportDefinition("shop-sales", "apps.operations.reports_shop.build_shop_sales", SALES_FIELDS, ("shop",),
                     required_action=rbac.Action.MANAGE_SHOP, title=gettext_noop("Shop sales by month and channel"),
                     deployment_aggregate=False, chart_hint="grouped_bar",
                     chart_spec=chart("month", (("sales", "currency_major"), ("refunds", "currency_major")),
                                      series=("channel",), currency=True)),
    # Decision 242 / SH3: the product-by-month table and the stock value table (tables, no chart).
    ReportDefinition("shop-product-sales", "apps.operations.reports_shop_products.build_shop_product_sales",
                     PRODUCT_FIELDS, ("shop",), required_action=rbac.Action.MANAGE_SHOP,
                     title=gettext_noop("Shop sales by product and month"), deployment_aggregate=False,
                     schedulable=False),
    ReportDefinition("shop-stock-value", "apps.operations.reports_shop_products.build_shop_stock_value",
                     STOCK_FIELDS, ("shop",), required_action=rbac.Action.MANAGE_SHOP,
                     title=gettext_noop("Shop stock value"), deployment_aggregate=False, schedulable=False),
)
