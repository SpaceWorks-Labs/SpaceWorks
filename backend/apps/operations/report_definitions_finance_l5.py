"""Lane L5 finance reports: the finance ledger (#94/#100), bookkeeping by FY and GST returns.

None runs deployment-wide (finance is per space), and none needs the removable rail.
Area reports carry the area manager's own action so each manager sees that area's money
(#100); `machines` rows are further narrowed to the manager's machine types by the
builder, so those are not schedulable (a scheduled copy has no viewer to narrow for).
"""

from apps.accounts import rbac
from apps.operations.report_types import ReportDefinition
from apps.operations.reports_bookkeeping_fy import RP_FIELDS, SUB_FIELDS
from apps.operations.reports_money_methods import FIELDS as METHOD_FIELDS
from apps.operations.reports_tax_gst import TABLE_FIELDS
from apps.operations.reports_tax_returns import B3_FIELDS, REGISTER_FIELDS, SUMMARY_FIELDS
from apps.payments.reports_finance_ledger import EVENT_FIELDS, FIELDS as LEDGER_FIELDS

_LEDGER = "apps.payments.reports_finance_ledger."
_OPS = "apps.operations."


def _ledger(key, builder, title, action, **extra):
    return ReportDefinition(key, _LEDGER + builder, LEDGER_FIELDS, required_action=action, title=title,
                            deployment_aggregate=False, required_feature="finance.ledger", chart_hint="grouped_bar",
                            **extra)


def _tax(key, builder, fields, title):
    return ReportDefinition(key, _OPS + builder, fields, required_action=rbac.Action.VIEW_FINANCE, title=title,
                            deployment_aggregate=False, required_feature="billing.tax")


L5_FINANCE_REPORT_DEFINITIONS = (
    _ledger("income-spending", "build_income_spending", "Income and spending by month and area",
            rbac.Action.VIEW_FINANCE),
    _ledger("finance-inventory", "build_finance_inventory", "Inventory and lending money",
            rbac.Action.EDIT_INVENTORY, schedulable=False),
    _ledger("finance-machines", "build_finance_machines", "Machine money", rbac.Action.MANAGE_MACHINES,
            schedulable=False),
    _ledger("finance-bookings", "build_finance_bookings", "Bookings and rooms money", rbac.Action.MANAGE_BOOKINGS,
            schedulable=False),
    _ledger("finance-events", "build_finance_events", "Events money", rbac.Action.MANAGE_EVENTS, schedulable=False),
    ReportDefinition("event-finance", _LEDGER + "build_event_finance", EVENT_FIELDS,
                     required_action=rbac.Action.MANAGE_EVENTS, title="Money per event against budget",
                     deployment_aggregate=False, required_feature="finance.ledger", schedulable=False),
    ReportDefinition("receipts-payments", _OPS + "reports_bookkeeping_fy.build_receipts_payments", RP_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Receipts and payments by financial year",
                     deployment_aggregate=False, required_feature="finance.ledger"),
    ReportDefinition("subscription-income", _OPS + "reports_bookkeeping_fy.build_subscription_income", SUB_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Membership income earned by financial year",
                     deployment_aggregate=False, required_feature="finance.ledger"),
    ReportDefinition("money-methods", _OPS + "reports_money_methods.build_money_methods", METHOD_FIELDS,
                     required_action=rbac.Action.VIEW_FINANCE, title="Money by provider and method",
                     deployment_aggregate=False, chart_hint="grouped_bar"),
    _tax("gstr1", "reports_tax_gst.build_gstr1", TABLE_FIELDS, "GSTR-1 outward supplies"),
    _tax("gstr3b", "reports_tax_returns.build_gstr3b", B3_FIELDS, "GSTR-3B summary and liability"),
    _tax("tax-summary", "reports_tax_returns.build_tax_summary", SUMMARY_FIELDS, "Tax charged by month"),
    _tax("documents-register", "reports_tax_returns.build_documents_register", REGISTER_FIELDS,
         "Documents register and numbering gaps"),
)
#: Builders that narrow rows to the viewer's finance areas, so the runner passes `actor`.
L5_ACTOR_REPORT_KEYS = frozenset({"income-spending", "finance-inventory", "finance-machines", "finance-bookings",
                                  "finance-events", "event-finance"})
