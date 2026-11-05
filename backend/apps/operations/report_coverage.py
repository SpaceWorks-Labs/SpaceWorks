from dataclasses import dataclass

from django.core import checks

from apps.makerspaces.module_registry import MODULE_KEYS
from apps.operations.report_registry import REPORT_REGISTRY
from apps.operations.report_coverage_contract import REPORT_COVERAGE_AREAS
from apps.separability.tombstones import tombstoned_app_labels


@dataclass(frozen=True)
class ModuleReportCoverage:
    kind: str
    reports: tuple[str, ...]


REPORT_MODULE_COVERAGE = {
    "presence": ModuleReportCoverage("substantive", ("presence-activity",)),
    "audit": ModuleReportCoverage("substantive", ("audit-activity",)),
    "organizations": ModuleReportCoverage("substantive", ("organization-membership",)),
    "platform": ModuleReportCoverage("substantive", ("platform-services", "platform-usage")),
    "public_inventory": ModuleReportCoverage("composite", ("inventory-control",)),
    "request_workflow": ModuleReportCoverage("substantive", ("loan-throughput",)),
    "staff_admin": ModuleReportCoverage("health_row", ("module-operational-health",)),
    "guest_handover": ModuleReportCoverage("composite", ("loan-throughput",)),
    "scanner": ModuleReportCoverage("substantive", ("qr-scans", "module-operational-health")),
    "printing": ModuleReportCoverage("substantive", ("printer-service",)),
    "telegram": ModuleReportCoverage("composite", ("communications-health",)),
    "evidence_uploads": ModuleReportCoverage("substantive", ("evidence-compliance",)),
    "qr_management": ModuleReportCoverage("composite", ("inventory-control",)),
    "bulk_import": ModuleReportCoverage("substantive", ("import-quality",)),
    "containers": ModuleReportCoverage("composite", ("inventory-control",)),
    "stock_transfers": ModuleReportCoverage("composite", ("inventory-control",)),
    "stocktake": ModuleReportCoverage("composite", ("inventory-control",)),
    "reports": ModuleReportCoverage("health_row", ("module-operational-health",)),
    "qr_print_batches": ModuleReportCoverage("composite", ("inventory-control",)),
    "asset_units": ModuleReportCoverage("composite", ("inventory-control",)),
    "procurement": ModuleReportCoverage("substantive", ("procurement-performance",)),
    "machines": ModuleReportCoverage("substantive", ("machine-usage", "module-operational-health")),
    "machine_service": ModuleReportCoverage("substantive", ("machine-service",)),
    "events": ModuleReportCoverage("substantive", ("event-attendance",)),
    "event_reimbursements": ModuleReportCoverage("health_row", ("module-operational-health",)),
    "bookings": ModuleReportCoverage("substantive", ("booking-utilization",)),
    "maintenance": ModuleReportCoverage("substantive", ("maintenance-activity",)),
    "membership": ModuleReportCoverage("substantive", ("member-activity", "community-engagement")),
    "notifications": ModuleReportCoverage("composite", ("communications-health",)),
    "email": ModuleReportCoverage("composite", ("communications-health",)),
    "sms": ModuleReportCoverage("substantive", ("communications-health", "platform-services", "module-operational-health")),
    "whatsapp": ModuleReportCoverage("substantive", ("communications-health", "platform-services", "module-operational-health")),
    "slack": ModuleReportCoverage("composite", ("communications-health",)),
    "webhook": ModuleReportCoverage("composite", ("communications-health",)),
    "mattermost": ModuleReportCoverage("composite", ("communications-health",)),
    "discord": ModuleReportCoverage("composite", ("communications-health",)),
    "payments": ModuleReportCoverage("substantive", ("payment-reconciliation",)),
    "member_accounts": ModuleReportCoverage("composite", ("community-engagement",)),
    "mobile": ModuleReportCoverage("composite", ("community-engagement",)),
    "devices": ModuleReportCoverage("health_row", ("module-operational-health",)),
}
REPORT_MODULE_COVERAGE["mobile"] = ModuleReportCoverage(
    "substantive", ("community-engagement", "mobile-devices", "mobile-auth", "communications-health"),
)

# Coverage associations are independent of the builders' actual source-module gates.
from apps.operations.report_definitions_ab import AB_REPORT_KEYS
from apps.operations.report_coverage_contract import required_report_modules
for _key, _modules in required_report_modules().items():
    if _key in AB_REPORT_KEYS:
        for _module in _modules:
            _coverage = REPORT_MODULE_COVERAGE[_module]
            REPORT_MODULE_COVERAGE[_module] = ModuleReportCoverage("substantive", tuple(dict.fromkeys((*_coverage.reports, _key))))

# Coverage associations describe the plan's area, not runtime source dependencies.
_MACHINE_AREA_REPORT_KEYS = (
    "machine-usage", "machine-usage-members", "machine-usage-heatmap", "machine-downtime",
    "maintenance-activity", "machine-service", "service-queue-times", "printer-jobs", "machine-errors", "warranty-expiry",
)
for _module in ("machines", "machine_service", "printing", "maintenance"):
    _coverage = REPORT_MODULE_COVERAGE[_module]
    REPORT_MODULE_COVERAGE[_module] = ModuleReportCoverage(_coverage.kind, tuple(dict.fromkeys((*_coverage.reports, *_MACHINE_AREA_REPORT_KEYS))))


REPORT_MODULE_COVERAGE["bookings"] = ModuleReportCoverage("substantive", (
    *REPORT_MODULE_COVERAGE["bookings"].reports, "booking-occupancy", "booking-lead-time", "booking-top-members",
))
REPORT_MODULE_COVERAGE["events"] = ModuleReportCoverage("substantive", (
    *REPORT_MODULE_COVERAGE["events"].reports, "event-signups", "event-revenue", "event-funnel",
    "event-checkin-times", "event-feedback-scores",
))


# These associations document coverage; the payment ledger is permanently core,
# and membership analytics do not require the optional member sign-in module.
REPORT_MODULE_COVERAGE.update({
    "membership": ModuleReportCoverage("substantive", (*REPORT_MODULE_COVERAGE["membership"].reports, "membership-growth", "member-retention", "membership-revenue")),
    "member_accounts": ModuleReportCoverage("substantive", (*REPORT_MODULE_COVERAGE["member_accounts"].reports, "membership-growth", "member-retention", "membership-revenue")),
    "payments": ModuleReportCoverage("substantive", (*REPORT_MODULE_COVERAGE["payments"].reports, "revenue-over-time", "payments-ageing", "cash-book")),
})
REPORT_MODULE_COVERAGE["devices"] = ModuleReportCoverage("substantive", ("device-health", "module-operational-health"))
# Release 2 L22: shop sales by month and channel, and the shop's own ledger money.
REPORT_MODULE_COVERAGE["shop"] = ModuleReportCoverage("substantive", ("shop-sales", "finance-shop"))
# Lane L25 (#163B): analytics is reported as a health row; its audit actions count as activity.
REPORT_MODULE_COVERAGE["analytics"] = ModuleReportCoverage("health_row", ("module-operational-health",))
# RP-5: the repairs family documents the per-parent repair and maintenance switches (#128 C-9),
# whose machine side lives with the machines module and the retired `maintenance` area.
from apps.operations.report_definitions_repairs import REPAIRS_REPORT_KEYS as _REPAIRS_KEYS  # noqa: E402
for _module in ("maintenance", "machines"):
    REPORT_MODULE_COVERAGE[_module] = ModuleReportCoverage(
        REPORT_MODULE_COVERAGE[_module].kind,
        tuple(dict.fromkeys((*REPORT_MODULE_COVERAGE[_module].reports, *sorted(_REPAIRS_KEYS)))))


@checks.register(checks.Tags.models)
def check_report_module_coverage(app_configs=None, **kwargs):
    errors = []
    missing = MODULE_KEYS - REPORT_MODULE_COVERAGE.keys()
    extra = REPORT_MODULE_COVERAGE.keys() - MODULE_KEYS - REPORT_COVERAGE_AREAS
    if missing or extra:
        errors.append(checks.Error(
            f"Report coverage differs from module registry; missing={sorted(missing)}, extra={sorted(extra)}.",
            id="operations.E001",
        ))
    for module_key, coverage in REPORT_MODULE_COVERAGE.items():
        if module_key in {"presence", "maintenance", "procurement"} and module_key in tombstoned_app_labels():
            continue
        from apps.makerspaces.module_registry import module_available
        if module_key in MODULE_KEYS and not module_available(module_key):
            continue
        for report_key in coverage.reports:
            definition = REPORT_REGISTRY.get(report_key)
            if definition is None:
                errors.append(checks.Error(
                    f"Module {module_key!r} references unknown report {report_key!r}.",
                    id="operations.E002",
                ))
            elif coverage.kind == "composite" and module_key not in definition.section_modules:
                errors.append(checks.Error(
                    f"Composite report {report_key!r} omits the {module_key!r} section gate.",
                    id="operations.E003",
                ))
    for definition in REPORT_REGISTRY.values():
        from apps.operations.report_sources import known_source
        unknown = {key for key in (*definition.required_modules, *definition.section_modules)
                   if not known_source(key)}
        if unknown:
            errors.append(checks.Error(
                f"Report {definition.key!r} references unknown modules {sorted(unknown)}.",
                id="operations.E004",
            ))
    return errors
