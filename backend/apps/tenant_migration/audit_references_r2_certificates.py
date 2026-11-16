"""Audit metadata IDs written by release-2 lane r2-idcards-best certificates (#199)."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP

EDGES = {
    ("event.certificate_design_approved", "template_revision_id"): AuditReference(
        R, "events.EventCertificateTemplateRevision"),
}
