"""Release-2 lane L2: communications, analytics and programme closures.

`event.*` actions sit under the dynamic event namespace, which withholds metadata at read
time, so those entries name the action only. The rest expose counts, kinds and flags --
never a message, an address, a link or a person.
"""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("event.broadcast_held", gettext_noop("Event broadcast sent with a five-second undo hold")),
    P("event.broadcast_cancelled_in_hold", gettext_noop("Event broadcast undone inside its hold")),
    P("event.broadcast_draft_saved", gettext_noop("Event broadcast draft saved")),
    P("event.approval_digest_sent", gettext_noop("Event approval digest sent")),
    P("event.feedback_anonymous_enabled", gettext_noop("Event feedback set to anonymous")),
    P("event.asset_usage_reconciled", gettext_noop("Event storage usage reconciled")),
    P("mentor.help_alert_routed", gettext_noop("Mentor help alert posted to a chat room"), ("channel", "delivered", "error")),
    P("mentor.help_alert_routes_changed", gettext_noop("Mentor help alert rooms changed"), ("count",)),
    P("organization.email_sender_updated", gettext_noop("Organisation event-email sender updated"),
      ("organization_id", "sender_name_set", "reply_to_set")),
    P("notification.inbox_snoozed", gettext_noop("Personal notification snoozed")),
    P("notification.inbox_archived", gettext_noop("Personal notification archived")),
    P("notification.inbox_restored", gettext_noop("Personal notification restored")),
    P("notification.browser_alert_subscribed", gettext_noop("Browser notifications switched on")),
    P("notification.browser_alert_unsubscribed", gettext_noop("Browser notifications switched off")),
    P("notification.destination_auto_disabled", gettext_noop("Chat room switched off after failed deliveries"),
      ("channel", "failures")),
    P("notification.escalated", gettext_noop("Unseen staff notice escalated"), ("feature", "event", "rooms")),
    P("organization.invitation_delivered", gettext_noop("Organisation invitation sent by email/chat"),
      ("organization_id", "emailed", "chat_offered")),
    P("hosting_request.changes_requested", gettext_noop("Hosting request: changes requested")),
    P("hosting_request.resubmitted", gettext_noop("Hosting request resubmitted"), ("changed_fields",)),
)
