"""Audit meta id paths of lane L1's public event surface (#21, #71, #73)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

PUBLIC_SURFACE_AUDIT_EDGES = {
    **{edge: AuditReference(R, "events.Event") for edge in (
        ("event.short_link.created", "event_id"), ("event.short_link.regenerated", "event_id"),
        ("event.publishing_changed", "event_id"), ("event.delivery_mode_changed", "event_id"),
    )},
    ("event.embed_policy_updated", "grant_id"): AuditReference(R, "makerspaces.ModuleSettingsGrant"),
}
