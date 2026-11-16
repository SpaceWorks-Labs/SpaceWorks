"""Audit metadata IDs written by parity E-B2 (hand-set event card roles)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

EDGES = {
    ("event_card.role_locked", "card_id"): AuditReference(R, "events.EventIdCard"),
    ("event_card.role_locked", "event_id"): AuditReference(R, "events.Event"),
}
