from django.utils.translation import gettext
from decimal import Decimal

from apps.tenant_migration.gate_runtime import tenant_write

from apps.operations.report_registry import (
    DEPLOYMENT_AGGREGATE_REPORT_KEYS,
    REPORT_KEYS,
    ReportNotFound,
    ReportResult,
    report_definition,
)
from apps.operations.reports_inventory import (
    _most_lent,
    _taken_items,
    _top_borrowers,
)
from apps.operations.reports_typed import typed_report_rows, typed_result_rows
from apps.operations.report_output import project_report_output
from apps.operations.report_definitions_finance_l5 import L5_ACTOR_REPORT_KEYS
from apps.operations.report_definitions_repairs import REPAIRS_ACTOR_REPORT_KEYS
from apps.operations.report_definitions_loan_context import LOAN_CONTEXT_REPORT_KEYS
from apps.operations.report_definitions_audit import AUDIT_VIEWER_REPORT_KEYS
from apps.operations.report_definitions_completeness import COMPLETENESS_ACTOR_REPORT_KEYS
from apps.operations.report_definitions_org_parity import ORG_PARITY_REPORT_KEYS
from apps.payments.money import money_text


DEFAULT_REPORT_LIMIT = 100
MAX_REPORT_LIMIT = 500


def report_data(
    report_key="summary", makerspace_id=None, *, limit=None, date_range=None,
    report_filters=None, grain="day", actor=None, platform_context=None,
):
    definition = report_definition(report_key, platform_context=platform_context)
    if makerspace_id is None and not definition.deployment_aggregate:
        raise ReportNotFound()
    subject = _authorize_subject(actor, makerspace_id, definition, report_filters)
    if not definition.previewable:
        # Export-only: the generic JSON analytics path must never become a second list.
        raise ReportNotFound()
    kwargs = dict(limit=_normalized_limit(limit), date_range=date_range, **(report_filters or {}))
    if report_key in {"presence-top-visitors", "audit-top-actors"}:
        kwargs["actor"] = actor
    if report_key in AUDIT_VIEWER_REPORT_KEYS:
        kwargs["viewer"] = actor
    if report_key == "booking-top-members":
        kwargs["actor"] = actor
    if report_key in {"member-retention", "membership-revenue", "membership-growth", "payments-ageing", "revenue-over-time", "cash-book", "payment-reconciliation", "refunds"}:
        kwargs["actor"] = actor
    if report_key in ORG_PARITY_REPORT_KEYS:
        kwargs["actor"] = actor  # O-B3: unit-scoped actors read their own subtree / own in-scope cash only
    if report_key in L5_ACTOR_REPORT_KEYS or report_key in REPAIRS_ACTOR_REPORT_KEYS or report_key in LOAN_CONTEXT_REPORT_KEYS or report_key in COMPLETENESS_ACTOR_REPORT_KEYS:
        kwargs["actor"] = actor
    from .report_definitions_machines import MACHINE_REPORT_KEYS
    if report_key in MACHINE_REPORT_KEYS or report_key in {"consumable-usage", "consumable-pools", "procurement-performance", "overdue-loans", "longest-loans", "qr-scan-actors", "certification-coverage", "printer-service", "fablab-health", "machine-service", "machine-access-grants", "device-adapter-activity"}:
        kwargs["actor"] = actor
    if definition.summary and makerspace_id is None:
        kwargs["limit"] = None  # Totals must include every eligible tenant.
    if definition.grains:
        kwargs["grain"] = grain
    if definition.platform_only:
        kwargs["platform_context"] = platform_context
    if report_key == "organization-membership" and makerspace_id is None:
        kwargs["platform_context"] = platform_context
    result = project_report_output(definition, definition.builder()(makerspace_id, **kwargs))
    if subject is not None:
        from apps.audit.services import record
        # Previews are GETs, but their disclosure audit is a tenant write.
        from apps.makerspaces.models import Makerspace
        # Subject adapters already enforce this route's tenant. Some subjects
        # (Booking) derive tenancy through a space rather than a direct field.
        space = Makerspace.objects.get(pk=makerspace_id)
        with tenant_write(space.pk):
            record(actor, "report.previewed", makerspace=space, target=subject,
                   meta={"report_key": definition.key})
    if definition.summary and isinstance(result, dict):
        return result
    if definition.summary and makerspace_id is None and isinstance(result, ReportResult):
        # The builder keeps per-tenant rows at deployment scope; the summary API has
        # always answered with deployment totals, summed over every eligible tenant.
        return {
            field: sum(row.get(field) or 0 for row in result.records)
            for field in result.field_order if field != "makerspace_id"
        }
    if not isinstance(result, ReportResult):
        return {"rows": result, "typed_rows": typed_report_rows(report_key, result)}
    rows = _matrix(result, json=True)
    return {
        "report_key": report_key,
        "rows": rows,
        "typed_rows": typed_result_rows(result, json_value),
        "meta": {"source": "live", "grain": grain, "rollup_through": None, **result.meta},
    }


def report_rows(
    report_key, makerspace_id=None, *, limit=None, date_range=None,
    report_filters=None, grain="day", actor=None, platform_context=None,
):
    definition = report_definition(report_key, for_export=True, platform_context=platform_context)
    if makerspace_id is None and not definition.deployment_aggregate:
        raise ReportNotFound()
    _authorize_subject(actor, makerspace_id, definition, report_filters)
    kwargs = dict(limit=limit, date_range=date_range, **(report_filters or {}))
    if report_key in {"presence-top-visitors", "audit-top-actors"}:
        kwargs["actor"] = actor
    if report_key in AUDIT_VIEWER_REPORT_KEYS:
        kwargs["viewer"] = actor
    if report_key == "booking-top-members":
        kwargs["actor"] = actor
    if report_key == "event-attendance-pdf":
        kwargs["actor"] = actor  # parity C19: the Money and Spending sections follow the viewer's finance view
    if report_key in {"member-retention", "membership-revenue", "membership-growth", "payments-ageing", "revenue-over-time", "cash-book", "payment-reconciliation", "refunds"}:
        kwargs["actor"] = actor
    if report_key in L5_ACTOR_REPORT_KEYS or report_key in REPAIRS_ACTOR_REPORT_KEYS or report_key in LOAN_CONTEXT_REPORT_KEYS or report_key in COMPLETENESS_ACTOR_REPORT_KEYS:
        kwargs["actor"] = actor
    from .report_definitions_machines import MACHINE_REPORT_KEYS
    if report_key in MACHINE_REPORT_KEYS or report_key in {"consumable-usage", "consumable-pools", "procurement-performance", "overdue-loans", "longest-loans", "qr-scan-actors", "certification-coverage", "printer-service", "fablab-health", "machine-service", "machine-access-grants", "device-adapter-activity"}:
        kwargs["actor"] = actor
    if definition.grains:
        kwargs["grain"] = grain
    if definition.platform_only:
        kwargs["platform_context"] = platform_context
    if report_key == "organization-membership" and makerspace_id is None:
        kwargs["platform_context"] = platform_context
    result = project_report_output(definition, definition.builder()(makerspace_id, **kwargs))
    if isinstance(result, ReportResult):
        return _export_matrix(result, grain)
    return result


def required_modules(report_key):
    return report_definition(report_key).required_modules


def _authorize_subject(actor, makerspace_id, definition, filters):
    from .report_subjects import authorize
    from apps.makerspaces.models import Makerspace
    from rest_framework.exceptions import PermissionDenied
    filters = filters or {}
    if (not definition.subject_kind and not definition.required_feature
            and not {"subject_kind", "subject_id"}.intersection(filters)):
        return
    if makerspace_id is None:
        raise PermissionDenied(gettext("Subject reports are tenant-local."))
    space = Makerspace.objects.get(pk=makerspace_id)
    return authorize(actor, space, definition, filters)


def validate_report_key(report_key, *, for_export=False, deployment_aggregate=False, platform_context=None):
    return report_definition(
        report_key, for_export=for_export, deployment_aggregate=deployment_aggregate,
        platform_context=platform_context,
    )


def _normalized_limit(limit):
    if limit is None:
        limit = DEFAULT_REPORT_LIMIT
    return max(0, min(int(limit), MAX_REPORT_LIMIT))


def _matrix(result, *, json):
    convert = json_value if json else (lambda value: value)
    return [
        list(result.field_order),
        *[
            [convert(record.get(field)) for field in result.field_order]
            for record in result.records
        ],
    ]


def _export_matrix(result, grain):
    # Provenance (source / grain / rollup_through) stays in the JSON response `meta` and is
    # deliberately NOT appended as export columns. It is one value per REPORT, not per row,
    # so appending it repeats itself on every line, and the export header of each report is
    # pinned to the fields the report registry declares -- the registry is the single source
    # of truth for a report's shape. Adding provenance to the file is a real product decision
    # about five already-shipped exports, and belongs to the owner rather than to this phase.
    return _matrix(result, json=False)


def json_value(value):
    if isinstance(value, Decimal):
        return money_text(value)
    return value
