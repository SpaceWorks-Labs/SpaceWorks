"""Release-2 lane L2: communications, analytics and programme closures.

`event.*` actions sit under the dynamic event namespace, which withholds metadata at read
time, so those entries name the action only. The rest expose counts, kinds and flags --
never a message, an address, a link or a person.
"""

from .presentation_catalog_types import P

ENTRIES = (
    P("event.broadcast_held", "Event broadcast sent with a five-second undo hold"),
    P("event.broadcast_cancelled_in_hold", "Event broadcast undone inside its hold"),
    P("event.broadcast_draft_saved", "Event broadcast draft saved"),
    P("event.approval_digest_sent", "Event approval digest sent"),
    P("event.feedback_anonymous_enabled", "Event feedback set to anonymous"),
    P("event.asset_usage_reconciled", "Event storage usage reconciled"),
    P("mentor.help_alert_routed", "Mentor help alert posted to a chat room", ("channel", "delivered", "error")),
    P("mentor.help_alert_routes_changed", "Mentor help alert rooms changed", ("count",)),
    P("organization.email_sender_updated", "Organisation event-email sender updated",
      ("organization_id", "sender_name_set", "reply_to_set")),
    P("notification.inbox_snoozed", "Personal notification snoozed"),
    P("notification.inbox_archived", "Personal notification archived"),
    P("notification.inbox_restored", "Personal notification restored"),
    P("notification.browser_alert_subscribed", "Browser notifications switched on"),
    P("notification.browser_alert_unsubscribed", "Browser notifications switched off"),
    P("notification.destination_auto_disabled", "Chat room switched off after failed deliveries",
      ("channel", "failures")),
    P("notification.escalated", "Unseen staff notice escalated", ("feature", "event", "rooms")),
    P("organization.invitation_delivered", "Organisation invitation sent by email/chat",
      ("organization_id", "emailed", "chat_offered")),
    P("hosting_request.changes_requested", "Hosting request: changes requested"),
    P("hosting_request.resubmitted", "Hosting request resubmitted", ("changed_fields",)),
)
