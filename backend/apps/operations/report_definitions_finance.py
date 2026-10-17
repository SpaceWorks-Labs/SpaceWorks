from apps.accounts import rbac
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_finance import LEDGER_FIELDS, REVENUE_FIELDS, CASH_FIELDS
from apps.operations.reports_accounting import FIELDS as ACCOUNTING_FIELDS
from apps.operations.reports_payments_ageing import FIELDS as AGEING_FIELDS
from apps.operations.report_charts_fg import REVENUE_CHART, CASH_CHART, AGEING_CHART
from apps.operations.org_report_aggregate import register_combine
from apps.operations.org_report_fg import combine_revenue, combine_cash, combine_ageing, combine_reconciliation

FINANCE_REPORT_DEFINITIONS = (
    ReportDefinition("payments-ledger", "apps.operations.reports_finance.build_payments_ledger", LEDGER_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Payments ledger", deployment_aggregate=False),
    ReportDefinition("revenue-over-time", "apps.operations.reports_finance.build_revenue_over_time", REVENUE_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Collected, owed and refunded by rail", chart_hint="stacked_bar",
                     grains=("day", "week", "month"), version=2, chart_spec=REVENUE_CHART),
    ReportDefinition("cash-book", "apps.operations.reports_finance.build_cash_book", CASH_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Cash book by local date", grains=("day", "week", "month"),
                     version=2, chart_hint="stacked_bar", chart_spec=CASH_CHART),
    ReportDefinition("payments-ageing", "apps.operations.reports_payments_ageing.build_payments_ageing", AGEING_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Outstanding debt ageing", chart_hint="stacked_bar",
                     chart_spec=AGEING_CHART),
    ReportDefinition("accounting-journal", "apps.operations.reports_accounting.build_accounting_journal", ACCOUNTING_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Accounting journal CSV", allowed_formats=("csv",),
                     deployment_aggregate=False),
)

# Money tracking is core: none of these requires the removable online rail.
register_combine("revenue-over-time", combine_revenue)
register_combine("cash-book", combine_cash)
register_combine("payments-ageing", combine_ageing)
register_combine("payment-reconciliation", combine_reconciliation)
