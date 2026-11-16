"""Audit metadata IDs written by release-2 lane L24 (price-drop refunds).

One `pricing.price_drop_refunds_opened` row lists the refund cases it opened and the charges they
refund; both lists follow their imported rows.
"""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

EDGES = {
    ("pricing.price_drop_refunds_opened", "case_ids"): AuditReference(R, "payments.RefundCase"),
    ("pricing.price_drop_refunds_opened", "payment_ids"): AuditReference(R, "payments.Payment"),
}
