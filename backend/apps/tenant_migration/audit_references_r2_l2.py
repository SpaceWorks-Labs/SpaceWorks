"""Release-2 lane L2 audit meta ids: inert source provenance after tenant import.

The rows they name (previews, rooms, inbox rows, organisations) either do not travel or
travel without their source ids being meaningful on the target, so they stay snapshots.
"""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

_S = AuditReference(AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT, None, "programme_source_provenance")

EDGES = {
    ("event.broadcast_held", "preview_id"): _S,
    ("mentor.help_alert_routed", "destination_id"): _S,
    ("organization.email_sender_updated", "organization_id"): _S,
    ("organization.invitation_delivered", "organization_id"): _S,
    ("notification.inbox_snoozed", "row_id"): _S,
    ("notification.inbox_archived", "row_id"): _S,
    ("notification.inbox_restored", "row_id"): _S,
}
