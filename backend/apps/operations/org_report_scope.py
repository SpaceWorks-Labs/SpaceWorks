"""Organization-owned makerspace scope for the reports dashboard.

COMBINED mode flattens rows across makerspaces, which the report-grouping invariant
otherwise forbids ("aggregate output groups by makerspace_id and never flattens
cross-tenant data"). A Stage-4 review flagged that correctly, and the invariant was
amended on 2026-08-20 with a bounded exception -- see docs/INVARIANTS.md under
"Reports/analytics extend one registry". This module is condition (1) of that exception:
the id set is resolved HERE, server-side, and never accepted from a client. Condition (2)
is the OWNER-only link filter below. Conditions (3) and (4) -- that a combined total only
ever ACCOMPANIES the per-makerspace breakdown, and that COMBINED is the only flattening
mode -- must be enforced by the aggregation layer that consumes this scope.
"""

from django.db.models import Exists, OuterRef

from apps.accounts import rbac
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.operations.report_registry import ReportDefinition
from apps.operations.report_scope import ReportScope, combined_report_scope
from apps.accounts.native_session import is_native_session
from apps.organizations.models import (
    Organization,
    OrganizationMakerspace,
    OrganizationMembership,
)


ORGANIZATION_REPORT_ACTIONS = frozenset({
    rbac.Action.MANAGE_MEMBERS,
    rbac.Action.VIEW_AUDIT,
    rbac.Action.MANAGE_MAKERSPACE,
    rbac.Action.VIEW_FINANCE,
    # Event attendance and booking utilisation are keyed to the area actions, so an
    # organization grant of that action (never a local role) is what admits them.
    rbac.Action.MANAGE_EVENTS,
    rbac.Action.MANAGE_BOOKINGS,
    rbac.Action.VIEW_INVENTORY,
    rbac.Action.EDIT_INVENTORY,
    rbac.Action.MANAGE_MACHINES,
})
EXCLUDED_ORGANIZATION_REPORT_KEYS = frozenset({
    "overdue-loans", "longest-loans", "qr-scan-actors",
    "presence-top-visitors", "audit-top-actors",
    "presence-activity-hours", "audit-activity-hours",
    "platform-services", "platform-usage",
    "active-loans", "returns", "top-borrowers",
    "machine-usage-members", "machine-usage-heatmap",
    "booking-top-members",
    # Tenant-local hour-of-week cells are intentionally not organization totals.
    "booking-occupancy",
    "booking-resource-utilization", "booking-resource-utilization-pdf", "booking-reservations", "booking-answers",
    "event-registrations", "event-feedback", "event-attendance-pdf", "event-orders",
    "event-equipment", "booking-equipment", "event-loan-timeline", "booking-loan-timeline",
    # One activity's consumable use is tenant-local stock and price context.
    "event-consumables", "booking-consumables",
    # Financial detail and accounting custody stay tenant-local. Different local
    # calendars also make a combined revenue/cash period misleading.
    "payments-ledger", "accounting-journal", "revenue-over-time", "cash-book",
    # Refund cases are tenant-local decisions in each space's own calendar month.
    "refunds",
    # Tenant accountability data: never flattened across an organization's spaces.
    "audit-trail",
    # Cohort anniversaries and month-end plan projections stay tenant-local; distinct
    # members and local-time snapshots cannot be flattened into one organization KPI.
    "member-retention", "membership-revenue",
    # Unique borrowers can span makerspaces, while the duration averages do not
    # expose the sample counts needed to combine them without bias.
    "loan-throughput",
    # Its rate_percent rows use heterogeneous, unexposed denominators (for example
    # public products versus active containers), so one weighted total is undefined.
    "inventory-control",
    # Import diagnostics intentionally retain their tenant/job context; flattening
    # failures and warning rates would hide which makerspace needs remediation.
    "import-quality",
    # The average order/receipt durations do not expose their qualifying sample
    # counts, so an organization average cannot be reconstructed correctly.
    "procurement-performance",
    # Delivery configuration and health are tenant-local, and repeated destination
    # counts plus per-status rates do not form one truthful organization total.
    "communications-health",
    # Active accounts are distinct-person metrics that may refer to the same person
    # in several owned makerspaces and therefore cannot be summed safely.
    "community-engagement",
    # Decision 223 (k): distinct people per space; one attendee at two owned spaces would double-count.
    "join-funnel",
    # Certified-member counts are distinct-person metrics per makerspace; one member
    # trained in two owned spaces would be double-counted by a naive sum.
    "certification-coverage",
    # Enabled/available/rollup state is per makerspace; combining it would mask the
    # specific unhealthy or stale tenant that an operator must repair.
    "module-operational-health",
    "machine-service",
    "printer-service",
    # Medians/percentiles cannot be reconstructed by averaging tenant summaries.
    "service-queue-times", "booking-lead-time", "event-checkin-times",
})

# v2 A+B definitions expose additive samples/denominators for these former exclusions.
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS - {"loan-throughput", "inventory-control", "procurement-performance"}


# v2 communications exposes additive cohorts and both rate denominators.
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS - {"communications-health"}
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS - {"machine-service"}
# Release 2 L4: tenant-local membership insights and the two person lists (register, win-back).
from apps.operations.report_definitions_membership_l4 import L4_MEMBERSHIP_REPORT_KEYS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | L4_MEMBERSHIP_REPORT_KEYS
from apps.operations.report_definitions_machine_sessions import SESSION_REPORT_KEYS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | SESSION_REPORT_KEYS
# Release 2 L3: the member-card issuance tile is tenant-local.
from apps.operations.report_definitions_cards import CARD_REPORT_KEYS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | CARD_REPORT_KEYS
# RP-5 repairs family: rows are narrowed to one viewer's areas and jobs in one space, the
# workload names technicians, and median repair hours cannot be summed across spaces.
from apps.operations.report_definitions_repairs import REPAIRS_REPORT_KEYS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | REPAIRS_REPORT_KEYS
# RP-3: donations money, campaigns, pledges and sponsor perks are tenant-local finance
# (each space's own causes, calendar and sponsors); never combined across an organization.
from apps.operations.report_definitions_donations import DONATION_REPORT_KEYS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | DONATION_REPORT_KEYS | {"finance-donations"}
# L5 finance books (area ledgers, FY bookkeeping, GST returns and the documents register) are
# per-space accounts with their own numbering and tax registration; they never combine across
# an organization. The L22 shop money and sales are per space too.
from apps.operations.report_definitions_finance_l5 import L5_FINANCE_REPORT_DEFINITIONS  # noqa: E402
from apps.operations.report_definitions_shop import SHOP_REPORT_DEFINITIONS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | {
    definition.key for definition in (*L5_FINANCE_REPORT_DEFINITIONS, *SHOP_REPORT_DEFINITIONS)}

# Parity O-B3: cash in hand, revenue by plan, the renewal forecast and approval times are per-space.
from apps.operations.report_definitions_org_parity import ORG_PARITY_REPORT_KEYS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | ORG_PARITY_REPORT_KEYS

# Decision 248: the area reports and people exports are per-space tables.
from apps.operations.report_definitions_completeness import COMPLETENESS_REPORT_KEYS  # noqa: E402
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS | COMPLETENESS_REPORT_KEYS


# Phase 1f F/G adds explicit local-period strategies and exposed denominators.
# These totals count memberships (a person in two spaces contributes twice).
EXCLUDED_ORGANIZATION_REPORT_KEYS = EXCLUDED_ORGANIZATION_REPORT_KEYS - {
    "member-retention", "membership-revenue", "revenue-over-time", "cash-book",
}


class OrganizationReportScopeError(ValueError):
    """Base error for a report definition the organization dashboard cannot use."""


class UnsupportedOrganizationReport(OrganizationReportScopeError):
    """The report key is deliberately unavailable to organization dashboards."""


class UnsupportedOrganizationReportAction(OrganizationReportScopeError):
    """The report requires authority outside the dashboard's safe vocabulary."""


def _validate_inputs(
    organization: Organization,
    definition: ReportDefinition,
) -> None:
    if not isinstance(organization, Organization):
        raise TypeError("organization must be a server-resolved Organization instance.")
    if organization.pk is None:
        raise ValueError("organization must be saved before resolving report scope.")
    if not isinstance(definition, ReportDefinition):
        raise TypeError("definition must be a ReportDefinition.")
    if definition.platform_only:
        from .report_types import ReportNotFound
        raise ReportNotFound()
    if definition.identity_bearing:
        raise UnsupportedOrganizationReport("Identity-bearing reports are tenant-only.")
    if definition.key in EXCLUDED_ORGANIZATION_REPORT_KEYS:
        raise UnsupportedOrganizationReport(
            f"Report {definition.key!r} is unavailable to organization dashboards."
        )
    if definition.required_action not in ORGANIZATION_REPORT_ACTIONS:
        raise UnsupportedOrganizationReportAction(
            f"Action {definition.required_action!r} is not supported by organization reports."
        )
    if any(
        not isinstance(module, str) or not module
        for module in definition.required_modules
    ):
        raise OrganizationReportScopeError(
            "Report source modules must be non-empty strings."
        )


def resolve_organization_report_scope(
    actor,
    organization: Organization,
    definition: ReportDefinition,
) -> ReportScope:
    """Resolve a combined scope using only the requested organization's OWNER grant."""
    _validate_inputs(organization, definition)

    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or getattr(actor, "pk", None) is None
        # Native device sessions are membership-only: no organization report scope.
        or is_native_session(actor)
    ):
        return combined_report_scope(Makerspace.objects.none())

    # Terms 1-3 deliberately share one membership query so the action cannot come
    # from a different organization or from a local makerspace role.
    active_grant = OrganizationMembership.objects.filter(
        organization=organization,
        organization__is_active=True,
        user=actor,
        status=OrganizationMembership.Status.ACTIVE,
        granted_actions__contains=[definition.required_action],
    )
    requested_owner_link = OrganizationMakerspace.objects.filter(
        organization=organization,
        relationship=OrganizationMakerspace.Relationship.OWNER,
        makerspace_id=OuterRef("pk"),
    )
    # Terms 1 and 4 share one link predicate: the requested organization itself
    # must be the OWNER, even if some other organization owns the same makerspace.
    makerspaces = Makerspace.objects.filter(
        Exists(active_grant),
        Exists(requested_owner_link),
    )
    # Term 5: importing, aborted, and archived spaces cannot serve reports.
    makerspaces = servable_queryset(makerspaces)
    # Term 6 (platform-reach consent) is gone: the superadmin is always on (#110), so
    # every servable owned space counts. Two deliberate non-filters, recorded so nobody
    # "fixes" them later:
    #   - hidden_from_central_directory is DIRECTORY visibility, not authorization; an
    #     owning organization still sees a space it owns that is off the central list.
    #   - there is no hidden LifecycleState (only ACTIVE/IMPORTING/ABORTED), so
    #     servable_queryset above already covers importing, aborted and archived.
    # Term 7: the reports module and every declared source module are required.
    makerspaces = makerspaces.filter(enabled_modules__contains=["reports"])
    from .report_sources import filter_sources
    makerspaces = filter_sources(makerspaces, definition.required_modules)

    return combined_report_scope(makerspaces)
