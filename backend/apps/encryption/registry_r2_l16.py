"""Scoped-PII fields added by release-2 lane L16 (technician contacts and issue reports).

A contractor's phone, email and chat handles, the Telegram chat proven by their opt-in,
and a reporter's name and email are personal data (#98, X-2): encrypted per space and
masked for a superadmin without an open PII window.
"""


def repairs_pii_fields(field):
    return (
        field("maintenance.TechnicianContact", "email", "makerspace_id", 254, "source", "none"),
        field("maintenance.TechnicianContact", "phone", "makerspace_id", 32, "source", "none"),
        field("maintenance.TechnicianContact", "telegram_handle", "makerspace_id", 64, "source", "none"),
        field("maintenance.TechnicianContact", "telegram_chat_id", "makerspace_id", 32, "source", "none"),
        field("maintenance.IssueReport", "reporter_name", "makerspace_id", 200, "source", "none"),
        field("maintenance.IssueReport", "reporter_email", "makerspace_id", 254, "source", "none"),
        field("maintenance.Incident", "involved_note", "makerspace_id", 200, "source", "none"),
    )
