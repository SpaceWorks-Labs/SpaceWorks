"""Audit meta id paths of lane L17's settings-authority layer (#101, #128 C-11)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

SETTINGS_AUTHORITY_AUDIT_EDGES = {
    **{edge: AuditReference(R, "makerspaces.ModuleSettingsGrant") for edge in (
        ("settings.changed", "grant_id"), ("settings.grant_created", "grant_id"),
        ("settings.grant_revoked", "grant_id"),
    )},
    **{edge: AuditReference(R, "makerspaces.ModuleSettingLock") for edge in (
        ("settings.lock_created", "lock_id"), ("settings.lock_released", "lock_id"),
    )},
}
