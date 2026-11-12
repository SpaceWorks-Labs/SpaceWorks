"""Canonical composition point for every report definition."""

from dataclasses import replace

from apps.operations.report_definitions_audit import AUDIT_REPORT_DEFINITIONS
from apps.operations.report_definitions_coverage import COVERAGE_REPORT_DEFINITIONS
from apps.operations.report_definitions_existing import EXISTING_REPORT_DEFINITIONS
from apps.operations.report_definitions_membership import MEMBERSHIP_REPORT_DEFINITIONS
from apps.operations.report_definitions_finance import FINANCE_REPORT_DEFINITIONS
from apps.operations.report_definitions_events import EVENT_REPORT_DEFINITIONS
from apps.operations.report_definitions_bookings import BOOKING_REPORT_DEFINITIONS
from apps.operations.report_definitions_hi import HI_REPORT_DEFINITIONS
from apps.operations.report_definitions_ab import AB_REPORT_DEFINITIONS, AB_REPORT_KEYS, register_ab_combines
from apps.operations.report_definitions_machines import MACHINE_REPORT_DEFINITIONS, MACHINE_REPORT_KEYS
from apps.operations.report_definitions_de import DE_REPORT_DEFINITIONS
from apps.operations.report_definitions_j import J_REPORT_DEFINITIONS
from apps.operations.report_definitions_repairs import REPAIRS_REPORT_DEFINITIONS
from apps.operations.report_definitions_loan_context import LOAN_CONTEXT_REPORT_DEFINITIONS
from apps.operations.report_definitions_completeness import COMPLETENESS_REPORT_DEFINITIONS
from apps.operations.report_definitions_org_parity import ORG_PARITY_REPORT_DEFINITIONS
from apps.operations.report_definitions_r2_final import R2_FINAL_REPORT_DEFINITIONS
from apps.operations.report_definitions_channels import CHANNEL_REPORT_DEFINITIONS
from apps.operations.report_types import (
    ReportDefinition,
    ReportNotExportable,
    ReportNotFound,
    ReportResult,
)


REPORT_DEFINITIONS = (
    *EXISTING_REPORT_DEFINITIONS, *COVERAGE_REPORT_DEFINITIONS, *AUDIT_REPORT_DEFINITIONS,
    *MEMBERSHIP_REPORT_DEFINITIONS,
    *FINANCE_REPORT_DEFINITIONS,
    *EVENT_REPORT_DEFINITIONS,
    *BOOKING_REPORT_DEFINITIONS,
    *HI_REPORT_DEFINITIONS,
    *DE_REPORT_DEFINITIONS,
    *REPAIRS_REPORT_DEFINITIONS,
    *LOAN_CONTEXT_REPORT_DEFINITIONS,
    *COMPLETENESS_REPORT_DEFINITIONS,
    *ORG_PARITY_REPORT_DEFINITIONS,
    *R2_FINAL_REPORT_DEFINITIONS,
    *CHANNEL_REPORT_DEFINITIONS,
)
# Area A+B replaces the shipped definitions without retaining duplicate catalog keys.
REPORT_DEFINITIONS = tuple(d for d in REPORT_DEFINITIONS if d.key not in AB_REPORT_KEYS) + AB_REPORT_DEFINITIONS
register_ab_combines()
REPORT_DEFINITIONS = tuple(d for d in REPORT_DEFINITIONS if d.key not in MACHINE_REPORT_KEYS) + MACHINE_REPORT_DEFINITIONS
REPORT_DEFINITIONS = tuple(d for d in REPORT_DEFINITIONS if d.key != "module-operational-health") + J_REPORT_DEFINITIONS
# Runtime entries disappear on a deployment tombstone; retention stays registered.
from apps.separability.tombstones import tombstoned_app_labels
from apps.operations.report_sources import source_app_labels
# Keep the exact declared omissions so coverage can distinguish a removed source
# from an accidentally missing report. The live catalogue remains the one registry.
TOMBSTONED_REPORT_KEYS = frozenset(
    d.key for d in REPORT_DEFINITIONS
    if source_app_labels(d.required_modules) & tombstoned_app_labels()
)
REPORT_DEFINITIONS = tuple(d for d in REPORT_DEFINITIONS if d.key not in TOMBSTONED_REPORT_KEYS)
# Declare infrastructure scope alongside data fields, without changing tenant
# builders' column order or propagating scope into subject-only definitions.
REPORT_DEFINITIONS = tuple(
    replace(d, fields=("makerspace_id", *d.fields))
    if d.deployment_aggregate and "makerspace_id" not in d.fields else d
    for d in REPORT_DEFINITIONS
)
REPORT_REGISTRY = {definition.key: definition for definition in REPORT_DEFINITIONS}
REPORT_KEYS = [definition.key for definition in REPORT_DEFINITIONS]
# The only definitions any deployment-wide (all-makerspaces) surface may enumerate or run.
DEPLOYMENT_AGGREGATE_REPORT_DEFINITIONS = tuple(
    definition for definition in REPORT_DEFINITIONS if definition.deployment_aggregate
)
DEPLOYMENT_AGGREGATE_REPORT_KEYS = [
    definition.key for definition in DEPLOYMENT_AGGREGATE_REPORT_DEFINITIONS
]


def report_definition(report_key, *, for_export=False, deployment_aggregate=False, platform_context=None):
    definition = REPORT_REGISTRY.get(report_key)
    if definition is None or (deployment_aggregate and not definition.deployment_aggregate):
        raise ReportNotFound()
    if definition.platform_only:
        if platform_context is None:
            raise ReportNotFound()
        from .platform_scope import require_platform_context
        require_platform_context(platform_context)
    from .report_validation import validate_report_definition
    validate_report_definition(definition)
    if for_export and not definition.exportable:
        raise ReportNotExportable()
    return definition


__all__ = [
    "DEPLOYMENT_AGGREGATE_REPORT_DEFINITIONS", "DEPLOYMENT_AGGREGATE_REPORT_KEYS",
    "REPORT_DEFINITIONS", "REPORT_KEYS", "REPORT_REGISTRY", "TOMBSTONED_REPORT_KEYS", "ReportDefinition",
    "ReportNotExportable", "ReportNotFound", "ReportResult", "report_definition",
]
