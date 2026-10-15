"""Batch resource authority and feature flags for paginated staff serializers."""

from apps.makerspaces.platform import feature_enabled

from . import booking_authority
from .booking_permissions import PERMISSIONS
from .models import BookableSpace


def features_for_page(rows):
    # select_related makerspaces are separate Python objects on each resource;
    # deduplicate by tenant ID before invoking the recovery-aware feature policy.
    makerspaces = {row.makerspace_id: row.makerspace for row in rows}
    return {pk: {
        "clone_enabled": feature_enabled(makerspace, "bookings.clone"),
        "staff_tools_enabled": feature_enabled(makerspace, "bookings.staff_tools"),
        "recurring_enabled": feature_enabled(makerspace, "bookings.recurring"),
        "staff_grants_enabled": feature_enabled(makerspace, "bookings.staff_grants"),
    } for pk, makerspace in makerspaces.items()}


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
