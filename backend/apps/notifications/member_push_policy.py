"""Re-evaluate tenant, owner, requester selection and device policy before delivery."""

from django.core.exceptions import ValidationError

from apps.accounts import rbac
from apps.integrations.destinations import NotificationScope
from apps.integrations.notification_catalog import is_notification_enabled
from apps.integrations.push import push_configured
from apps.integrations.recipients_selection import feature_available, has_selection, requester_selected
from apps.makerspaces.models import MakerspaceMembership
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import is_servable
from apps.notifications.inbox import eligible_owner
from apps.notifications.inbox_scope import validate_notification_scope
from apps.notifications.preferences import personal_enabled


def global_enabled(row):
    space = row.makerspace
    return (
        row.audience == "member" and is_servable(space)
        and feature_enabled(space, "mobile.push")
        and is_notification_enabled(space, row.feature, "native_push")
        and push_configured() and feature_available(space, row.feature)
        and module_enabled(space, "notifications")
        and feature_enabled(space, "notifications.member_inbox")
    )


def recipient_allowed(row):
    space = row.makerspace
    if not eligible_owner(space, row.user_id):
        return False
    if not rbac.scope_notification_policy(
        MakerspaceMembership.objects.all(), makerspace_id=space.pk,
    ).filter(user_id=row.user_id, status="active", receives_notifications=True).exists():
        return False
    try:
        validate_notification_scope(row.scope)
    except ValidationError:
        return False
    scope = NotificationScope.from_dict(row.scope)
    if has_selection(space, row.feature, row.event, scope) and not requester_selected(
        space, row.feature, row.event, scope,
    ):
        return False
    return personal_enabled(space, row.user_id, row.feature, "native_push", event=row.event)


def device_allowed(device, row):
    grant = device.device_grant
    registration = grant.registration
    return (
        device.active and device.makerspace_id == row.makerspace_id and device.user_id == row.user_id
        and grant.status == "active" and grant.user_id == row.user_id
        and registration.status == "approved" and registration.makerspace_id is None
    )
