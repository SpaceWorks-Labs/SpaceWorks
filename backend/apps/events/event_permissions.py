"""Event permissions are deliberately separate from makerspace RBAC actions."""

from apps.makerspaces.resource_grants_models import validate_permission_set

EDIT_DETAILS = "edit_details"
MANAGE_REGISTRATIONS = "manage_registrations"
MANAGE_INVITATIONS = "manage_invitations"
CHECK_IN = "check_in"
PUBLISH_SCHEDULE = "publish_schedule"
REVIEW_APPLICATIONS = "review_applications"
MANAGE_HACKATHON = "manage_hackathon"
MANAGE_TEAM = "manage_team"
MANAGE_VOLUNTEERS = "manage_volunteers"
MENTOR_QUEUE = "mentor_queue"
JUDGE = "judge"
VIEW_SPONSOR_TRACK = "view_sponsor_track"
PROGRAMME_PERMISSIONS = (
    REVIEW_APPLICATIONS, MANAGE_HACKATHON, MANAGE_TEAM, MANAGE_VOLUNTEERS,
    MENTOR_QUEUE, JUDGE, VIEW_SPONSOR_TRACK,
)
PERMISSIONS = (
    EDIT_DETAILS, MANAGE_REGISTRATIONS, MANAGE_INVITATIONS, CHECK_IN, PUBLISH_SCHEDULE,
    *PROGRAMME_PERMISSIONS,
)
# Read the event shell with any permission; None always means full manager authority.
VIEW = "view"


def validate_permissions(value):
    validate_permission_set(value, PERMISSIONS)
