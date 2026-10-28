"""Inventory/loans and consumables catalog entries and organization registration."""

from apps.accounts import rbac
from apps.operations.report_types import ReportDefinition
from apps.operations import reports_ab_activity as activity, reports_ab_assets as assets
from apps.operations import reports_ab_consumables as consumables, reports_ab_loans as loans
from apps.operations import reports_ab_movements as movements, reports_ab_stock as stock
from apps.operations.reports_ab_procurement import FIELDS as PROCUREMENT_FIELDS


def chart(x, values, *, series=(), time=False, partition="tenant", currency=None, top=None, negatives=False):
    if partition in ("currency", "unit"):
        series = ("makerspace_id", *series)
    return dict(series=list(series), x={"field": x, "kind": "time" if time else "category"},
        values=[{"field": field, "unit": unit} for field, unit in values], currency_field=currency,
        partition=partition, negatives="allow" if negatives else "clip",
        truncation={"top_n": top, "other_label": "Other"} if top else None,
        alt_template="{count} observations")


def definition(key, module, fields, required, *, action=rbac.Action.VIEW_INVENTORY, sections=(),
               identity=False, hint="bar", grains=False, version=1, spec=None):
    return ReportDefinition(key, f"apps.operations.{module}.build_{key.replace('-', '_')}", fields,
        required_modules=required, required_action=action, section_modules=sections,
        title=key.replace("-", " ").title(), identity_bearing=identity,
        schedulable=not identity and key != "summary", deployment_aggregate=not identity, version=version,
        summary=key == "summary", exportable=key != "summary",
        grains=("day", "week", "month") if grains else (), chart_hint=hint, chart_spec=spec)


AB_REPORT_DEFINITIONS = (
    definition("most-lent", "reports_ab_loans", loans.MOST_FIELDS, ("request_workflow",), version=2,
        grains=True, hint="multi_line", spec=chart("period", (("total_quantity_lent", "units"),),
                                                  series=("product_id", "product_name"), time=True, top=5)),
    definition("asset-usage", "reports_ab_assets", assets.ASSET_FIELDS, ("asset_units", "request_workflow"),
        spec=chart("asset_id", (("times_lent", "loans"),), top=10)),
    definition("loan-throughput", "reports_ab_loans", loans.THROUGHPUT_FIELDS, ("request_workflow",),
        sections=("guest_handover",), version=2, grains=True, hint="multi_line",
        spec=chart("period", (("issued_units", "units"), ("returned_units", "units"), ("lost_units", "units")), time=True)),
    definition("inventory-utilisation", "reports_ab_stock", stock.UTIL_FIELDS, ("public_inventory",),
        sections=("asset_units", "request_workflow"), grains=True, hint="line",
        spec=chart("period", (("utilisation_percent", "percent"),), series=("row_kind", "product_id", "asset_id"), time=True)),
    definition("overdue-loans", "reports_ab_assets", assets.OVERDUE_FIELDS, ("request_workflow",),
        action=rbac.Action.VIEW_AUDIT, identity=True, grains=True, hint="line",
        spec=chart("period", (("overdue_count", "loans"),), time=True, partition=None)),
    definition("damaged-lost", "reports_ab_stock", stock.DAMAGE_FIELDS, ("public_inventory",), version=2,
        hint="grouped_bar", spec=chart("product_name", (("damage_rate_percent", "percent"), ("loss_rate_percent", "percent")))),
    definition("longest-loans", "reports_ab_assets", assets.LONG_FIELDS, ("request_workflow",),
        identity=True, action=rbac.Action.VIEW_AUDIT, spec=chart("request_id", (("loan_days", "days"),), partition=None, top=10)),
    definition("stock-health", "reports_ab_stock", stock.HEALTH_FIELDS, ("public_inventory",), grains=True, hint="line",
        spec=chart("period", (("days_observed_out_of_stock", "observed product-days"),), series=("product_id", "row_kind"), time=True)),
    definition("request-funnel", "reports_ab_loans", loans.FUNNEL_FIELDS, ("request_workflow",), grains=True, hint="funnel",
        spec=chart("stage", (("count", "requests"),), series=("period", "row_kind", "approval_bucket"))),
    definition("problem-reports", "reports_ab_activity", activity.PROBLEM_FIELDS, ("guest_handover",), grains=True, hint="multi_line",
        spec=chart("period", (("opened_count", "reports"), ("resolved_count", "reports")), time=True)),
    definition("inventory-watch-demand", "reports_ab_activity", activity.WATCH_FIELDS, ("public_inventory",),
        spec=chart("product_name", (("waiting_count", "watches"),), top=10)),
    definition("summary", "reports_ab_stock", stock.SUMMARY_FIELDS, ("public_inventory",),
        sections=("asset_units", "request_workflow"), version=2, hint="donut",
        spec=chart("makerspace_id", tuple((f"asset_{s}", "assets") for s in
                   ("available", "reserved", "issued", "damaged", "lost", "maintenance", "retired")))),
    definition("qr-scans", "reports_ab_activity", activity.QR_FIELDS, ("scanner",), version=2, grains=True, hint="heatmap",
        spec=chart("hour_of_week", (("count", "scans"),), series=("period", "context", "target_type", "target_id"))),
    definition("qr-scan-actors", "reports_ab_activity", activity.QR_ACTOR_FIELDS, ("scanner",), identity=True,
        action=rbac.Action.VIEW_AUDIT, spec=chart("actor_id", (("count", "scans"),), partition=None, top=10)),
    definition("inventory-control", "reports_ab_movements", movements.CONTROL_FIELDS, (), version=2, grains=True, hint="line",
        sections=("public_inventory", "qr_management", "containers", "stock_transfers", "stocktake", "qr_print_batches", "asset_units"),
        spec=chart("period", (("count", "records"),), series=("module_key", "metric_key", "dimension"), time=True)),
    definition("consumable-usage", "reports_ab_consumables", consumables.USAGE_FIELDS, ("machines",),
        action=rbac.Action.MANAGE_MACHINES, sections=("machine_service",), grains=True, hint="multi_line",
        spec=chart("period", (("consumed_quantity", "measurement_unit"), ("cost_total_minor", "minor currency units")),
                   series=("material", "source", "measurement_unit", "currency"), time=True,
                   partition="currency", currency="currency", negatives=True)),
    definition("consumable-pools", "reports_ab_consumables", consumables.POOL_FIELDS, ("machines",),
        action=rbac.Action.MANAGE_MACHINES,
        spec=chart("material", (("remaining_quantity", "measurement_unit"), ("low_threshold", "measurement_unit")),
                   series=("measurement_unit",), partition="unit")),
    # One To-Buy list, two switches (#97): readable while either parent's is on.
    definition("procurement-performance", "reports_ab_procurement", PROCUREMENT_FIELDS, ("inventory.tobuy|machines.tobuy",),
        action=rbac.Action.EDIT_INVENTORY, version=2, grains=True, hint="stacked_bar",
        sections=("printing", "machines"),
        spec=chart("period", (("units", "units"),), series=("kind", "item_name", "lead_time_bucket"), time=True, top=10)),
    definition("stock-transfers", "reports_ab_movements", movements.TRANSFER_FIELDS, ("stock_transfers",),
        action=rbac.Action.EDIT_INVENTORY, grains=True, hint="stacked_bar",
        spec=chart("period", (("quantity", "units"),), time=True, series=("status", "source_makerspace_id", "destination_makerspace_id"))),
    definition("stocktake-variance", "reports_ab_movements", movements.VARIANCE_FIELDS, ("stocktake",),
        action=rbac.Action.EDIT_INVENTORY, grains=True, hint="bar",
        spec=chart("period", (("variance_quantity", "units"),), time=True, series=("product_id", "asset_id", "item_label"), negatives=True)),
)

AB_REPORT_KEYS = frozenset(d.key for d in AB_REPORT_DEFINITIONS)


def register_ab_combines():
    from apps.operations.org_report_aggregate import register_combine
    from apps.operations.org_report_ab import combine_for
    for definition in AB_REPORT_DEFINITIONS:
        if not definition.identity_bearing:
            register_combine(definition.key, combine_for(definition.key))
