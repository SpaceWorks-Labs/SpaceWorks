"""Audit metadata IDs written by U-C's interactive account merge (`account.merged`).

The merged account is a shell and the merge record is a platform row that never travels
(data_export `classification_unified_accounts`), so both IDs stay source-local snapshots.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    ("account.merged", "source_id"): AuditReference(S, "accounts.User"),
    ("account.merged", "record_id"): AuditReference(S, "accounts.AccountMergeRecord"),
}
