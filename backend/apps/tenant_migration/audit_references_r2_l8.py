"""Release-2 lane L8 audit meta ids: key jobs are deployment-local and never travel."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT

EDGES = {
    (action, "job_id"): AuditReference(S, "encryption.KeyRotationJob")
    for action in (
        "encryption.key_rotated", "encryption.key_rotation_completed", "encryption.emergency_rekey_started",
        "encryption.emergency_rekey_completed", "encryption.search_key_rotation_started",
        "encryption.search_reindexed", "encryption.key_job_failed",
    )
}
