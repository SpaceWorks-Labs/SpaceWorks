"""Batch resource authority and feature flags for paginated staff serializers."""

from apps.makerspaces.capability_eligibility import configuration_feature_enabled
from apps.makerspaces.servability import is_servable

from . import booking_authority
from .booking_permissions import PERMISSIONS
from .models import BookableSpace


def features_for_page(rows):
    # select_related makerspaces are separate Python objects on each resource;
    # deduplicate by tenant ID before invoking the recovery-aware feature policy.
    makerspaces = {row.makerspace_id: row.makerspace for row in rows}
    features = {
        "clone_enabled": "bookings.clone",
        "staff_tools_enabled": "bookings.staff_tools",
        "passes_enabled": "bookings.passes",
        "checkin_enabled": "bookings.checkin",
        "recurring_enabled": "bookings.recurring",
        "broadcasts_enabled": "bookings.broadcasts",
        "staff_grants_enabled": "bookings.staff_grants",
    }
    result = {}
    for pk, makerspace in makerspaces.items():
        # Evaluate the live recovery gate once for this response, then use the
        # same configuration policy as platform.feature_enabled for each flag.
        # Archival remains a liveness decision, as on the detail capability path.
        servable = is_servable(makerspace, allow_archived=True)
        result[pk] = {
            field: servable and configuration_feature_enabled(makerspace, key)
            for field, key in features.items()
        }
    return result


def authority_for_page(actor, rows):
    ids = {row.pk for row in rows}
    if not ids:
        return {}
    managers = set(booking_authority.spaces_for(
        actor, None, BookableSpace.objects.filter(pk__in=ids),
    ).values_list("pk", flat=True))
    permissions = {}
    grants = booking_authority.active_grants(actor, space_ids=ids)
    for space_id, values in grants.values_list("space_id", "permissions"):
        permissions.setdefault(space_id, set()).update(set(values) & set(PERMISSIONS))
    return {pk: (pk in managers, list(PERMISSIONS) if pk in managers else sorted(permissions.get(pk, set())))
            for pk in ids}
