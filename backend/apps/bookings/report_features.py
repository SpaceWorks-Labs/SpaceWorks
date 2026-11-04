"""Request-local report capability projection; never a substitute for authorization."""

from apps.accounts import rbac
from apps.makerspaces.platform import feature_enabled, module_enabled


def features_for_resource(actor, resource, authority, context):
    manager, permissions = authority
    if actor is None or "manage_reservations" not in permissions:
        return []
    cache = context.setdefault("booking_report_features", {})
    tenant = resource.makerspace
    if tenant.pk not in cache:
        enabled = []
        if module_enabled(tenant, "reports") and (
                rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, tenant.pk)
                or rbac.can(actor, rbac.Action.VIEW_AUDIT, tenant.pk)):
            enabled = [key for key, feature in (
                ("analytics", "bookings.analytics"), ("exports", "bookings.exports"),
                ("pdf", "bookings.utilization_pdf"),
            ) if feature_enabled(tenant, feature)]
        cache[tenant.pk] = enabled
    return [key for key in cache[tenant.pk] if key != "pdf" or manager]
