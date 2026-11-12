"""Machine-service notices: which STAFF get them is selectable per event and machine type (decision 343).

The `printing` notification family is machine service's (decision 340b). Its staff legs already resolve
through `staff_notifications.staff_user_ids_for_feature(..., scope)`, which honours an explicit selection
once a rule covers the job's machine type (`RecipientMachineTypeScope`), and otherwise keeps today's
action-based audience. So a space with no rules behaves exactly as before.

The member's own notices are NOT part of this selection: for a staff-only family `requester_selected`
answers yes, so a staff rule never silences the requester, and rules may name roles or people only.
"""

from django.utils.translation import gettext

from .models_recipients import NotificationRecipientKind
from .notification_enums import NotificationFeature

STAFF_ONLY_FEATURES = frozenset({NotificationFeature.PRINTING})

# Every machine-service notice with a staff leg: the lifecycle (`machines.notifications_p2_service.EVENTS`),
# the job flow minus its owner-only reminders (`notifications_job_flow`), and a session that stopped itself.
STAFF_EVENTS = {
    NotificationFeature.PRINTING: (
        "submitted", "accepted", "rejected", "started", "completed", "failed", "cancelled", "collected",
        "reprinted", "changes_requested", "resubmitted", "quoted", "quote_approved", "quote_declined",
        "quote_expired", "requeued", "uncollected", "no_show_flagged", "session_auto_stopped",
    ),
}
_MEMBER_KINDS = frozenset({NotificationRecipientKind.REQUESTER, NotificationRecipientKind.MEMBERS})


def selectable_events(feature, catalogue_events):
    return STAFF_EVENTS.get(feature, tuple(catalogue_events))


def refusal(feature, event, rules):
    """Why a rule set may not be saved for this staff-only family, or "" when it may."""
    if feature not in STAFF_ONLY_FEATURES:
        return ""
    if event not in STAFF_EVENTS[feature]:
        return gettext("This machine-service notice has no staff recipients to choose.")
    if any(rule.get("kind") in _MEMBER_KINDS for rule in rules):
        return gettext("Machine-service notices to the member are not chosen here; pick roles or people.")
    return ""
