"""Event permissions are deliberately separate from makerspace RBAC actions."""

from apps.makerspaces.resource_grants_models import validate_permission_set

EDIT_DETAILS = "edit_details"
MANAGE_REGISTRATIONS = "manage_registrations"
MANAGE_INVITATIONS = "manage_invitations"
CHECK_IN = "check_in"
PUBLISH_SCHEDULE = "publish_schedule"
PERMISSIONS = (
    EDIT_DETAILS, MANAGE_REGISTRATIONS, MANAGE_INVITATIONS, CHECK_IN, PUBLISH_SCHEDULE,
)
# Read the event shell with any permission; None always means full manager authority.
VIEW = "view"


def validate_permissions(value):
    validate_permission_set(value, PERMISSIONS)
