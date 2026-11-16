"""Parity O-B4 part 2 audit meta ids: a staff card and its membership travel with the space and remap."""
from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
CARD, MEMBERSHIP = "card_designs.StaffCard", "makerspaces.MakerspaceMembership"
_ACTIONS = ("issued", "auto_issued", "reissued", "revoked", "printed", "downloaded")

EDGES = {
    **{(f"staff_card.{action}", "card_id"): AuditReference(R, CARD) for action in _ACTIONS},
    ("staff_card.issued", "membership_id"): AuditReference(R, MEMBERSHIP),
    ("staff_card.auto_issued", "membership_id"): AuditReference(R, MEMBERSHIP),
    ("staff_card.auto_issue_skipped", "membership_id"): AuditReference(R, MEMBERSHIP),
}
