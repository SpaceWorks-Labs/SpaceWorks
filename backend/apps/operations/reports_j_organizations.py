"""Owner-organization funnel; repeated owner links must never multiply its people."""

from collections import defaultdict

from django.utils import timezone

from apps.organizations.models import Organization, OrganizationInvitation, OrganizationMakerspace, OrganizationMembership
from apps.operations.platform_scope import platform_analytics_spaces, require_platform_context
from apps.operations.reports_common import apply_range
from apps.operations.reports_j_common import area_spaces, calendar_range, period, rate, result
from apps.operations.report_fields_j import ORGANIZATION_FIELDS as FIELDS, ORGANIZATION_COUNTS as COUNTS



def _cohorts(org_id, date_range, grain):
    date_range = calendar_range(date_range)
    groups, now = defaultdict(lambda: dict.fromkeys(COUNTS, 0)), timezone.now()
    invitations = apply_range(OrganizationInvitation.objects.filter(organization_id=org_id), "created_at", date_range)
    for row in invitations.values("created_at", "redeemed_at", "revoked_at", "expires_at").iterator():
        state = groups[period(row["created_at"], grain)]
        state["invitations"] += 1
        outcome = "redeemed" if row["redeemed_at"] else "revoked" if row["revoked_at"] else "expired" if row["expires_at"] <= now else "open_invitations"
        state[outcome] += 1
    memberships = apply_range(OrganizationMembership.objects.filter(organization_id=org_id), "created_at", date_range)
    for row in memberships.values("created_at", "status").iterator():
        state = groups[period(row["created_at"], grain)]
        state["memberships"] += 1
        state[f"{row['status']}_memberships"] += 1
    return [{"period": bucket, "organization_id": org_id, **row,
             "redemption_percent": rate(row["redeemed"], row["invitations"])} for bucket, row in sorted(groups.items())]


def organization_membership_data(organization, scope, *, limit, date_range=None, grain="day"):
    """The view authorizes this global organization before supplying its row.

    Unlike business roll-ups, global organization membership does not require a
    tenant to exist. Its total therefore survives an empty OWNER-space scope.
    """
    if not isinstance(organization, Organization) or not organization.pk:
        raise TypeError("A server-resolved organization is required.")
    from apps.operations.org_reports import _payload, _validate_inputs
    from apps.operations.report_registry import REPORT_REGISTRY
    _validate_inputs(REPORT_REGISTRY["organization-membership"], scope, limit)
    rows = _cohorts(organization.pk, date_range, grain)
    return _payload("organization-membership", "weighted_rate",
                    [{"makerspace_id": pk, "rows": rows[:limit]} for pk in scope.makerspace_ids], rows[:limit])


def build_organization_membership(makerspace_id, *, limit=None, date_range=None, grain="day", platform_context=None):
    if makerspace_id is None:
        ctx = require_platform_context(platform_context)
        from apps.makerspaces.servability import servable_queryset
        spaces = {space.pk: space for space in servable_queryset(platform_analytics_spaces(ctx))}
    else:
        spaces = {space.pk: space for space in area_spaces(makerspace_id)}
    links = list(OrganizationMakerspace.objects.filter(makerspace_id__in=spaces, relationship="owner",
                                                      organization__is_active=True).values("makerspace_id", "organization_id"))
    records, cohorts = [], {}
    for link in links:
        org_id = link["organization_id"]
        if org_id not in cohorts:
            cohorts[org_id] = _cohorts(org_id, date_range, grain)
        records.extend({"makerspace_id": link["makerspace_id"], **row} for row in cohorts[org_id])
    if makerspace_id is None:
        # Only genuinely unlinked global organizations receive a deployment row;
        # an organization linked solely to hidden tenants cannot use this path.
        for org_id in Organization.objects.filter(is_active=True, makerspace_links__isnull=True).values_list("pk", flat=True):
            records.extend({"makerspace_id": None, **row} for row in _cohorts(org_id, date_range, grain))
    return result(FIELDS, records, makerspace_id, limit,
                  definition="Owner organization invitation/membership creation cohorts, current outcomes, UTC calendar; owner links repeat the same organization cohort.")
