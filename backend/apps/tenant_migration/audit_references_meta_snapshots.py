"""Source-local snapshot AuditLog meta references for portable tenant archives.

Split from `audit_references_meta.py` to keep that file under the size ceiling; the
declarations are unchanged and merged into AUDIT_META_REFERENCES there.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition


def _reference(disposition, model, *edges):
    return {edge: AuditReference(disposition, model) for edge in edges}


S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

SNAPSHOT_AUDIT_EDGES = {}
SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "backup.RestoreOperation",
        ("backup.quarantine_acknowledged", "restore_id"),
    )
)
SNAPSHOT_AUDIT_EDGES.update(
    _reference(S, "integrations.EmailLog", ("email.retried", "email_log_id"))
)
SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "accounts.User", ("encryption.write_fence_closed", "actor_id"),
        ("encryption.write_fence_opened", "actor_id"),
    )
)
# Revoking an organization membership names the person it revoked. SOURCE_LOCAL_SNAPSHOT
# rather than REMAP because the membership itself is an omitted model that never travels
# with a tenant, so asserting a live binding for the id it mentions would be a claim the
# archive cannot keep. Sibling created/updated events emit the same key but pick their
# action with a conditional expression, so the AST guard reports them as dynamic rather
# than as declared paths.
SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "accounts.User", ("organization.membership_deleted", "user_id"),
    )
)
from .audit_references_organization_audience import declarations as organization_audience_references
SNAPSHOT_AUDIT_EDGES.update(organization_audience_references(_reference, S))

SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "organizations.OrganizationMembership",
        ("organization.invitation_redeemed", "membership_id"),
    )
)
SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "makerspaces.Makerspace",
        ("event.host_waiver_accepted", "via_makerspace_id"),
        ("inventory.asset_moved_makerspace", "new_makerspace_id"),
        ("inventory.asset_moved_makerspace", "old_makerspace_id"),
        ("payment.created", "via_makerspace_id"),
        ("qr.rebound", "new_makerspace_id"),
        ("stock_transfer.received", "source_makerspace_id"),
    )
)
SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "makerspaces.MakerspaceArchiveRequest",
        ("makerspace.archive_request_approved", "archive_request_id"),
        ("makerspace.archive_request_declined", "archive_request_id"),
        ("makerspace.archive_request_withdrawn", "archive_request_id"),
        ("makerspace.archive_requested", "archive_request_id"),
    )
)
SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "payments.ProcessedStripeEvent",
        ("payment.checkout_expired", "stripe_event_id"),
        ("payment.double_paid_refund_required", "stripe_event_id"),
        ("payment.paid_after_terminal", "stripe_event_id"),
        ("payment.paid_online", "stripe_event_id"),
    )
)
SNAPSHOT_AUDIT_EDGES.update(
    _reference(
        S, "accounts.MemberClaimCode",
        ("presence.ended_claim_revoked", "claim_session_id"),
    )
)
SNAPSHOT_AUDIT_EDGES.update(
    _reference(S, "boxes.QrScanEvent", ("qr.scanned", "scan_id"))
)
