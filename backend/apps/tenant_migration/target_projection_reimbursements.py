"""Import resets for stage forms, reimbursements and the payout ledger.

History and money travel unchanged. What resets is operational authority: an imported
programme is paused and closed to new requests until finance reconciles it, imported
stage assignments are inert, and upload leases and source bucket versions never apply
on the target. Lane D shares these RESET declarations.
"""
from django.utils import timezone

from .target_projection_types import TargetField

_PAUSE = "Imported travel support stays paused until target finance reconciles reservations and counters."
_INERT = "Imported stage work is inert history until target staff reactivate it."
_LEASE = "Source upload leases and bucket version identities never apply on the target."

TARGET_FIELDS = {
    ("event_reimbursements.ReimbursementProgramme", "enabled"): TargetField(False, reason=_PAUSE),
    ("event_reimbursements.ReimbursementProgramme", "imported_paused"): TargetField(True, reason=_PAUSE),
    ("event_reimbursements.ReimbursementProgramme", "request_opens_at"): TargetField(None, reason=_PAUSE),
    ("event_reimbursements.ReimbursementProgramme", "request_closes_at"): TargetField(resolver=timezone.now, reason=_PAUSE),
    ("events.StageFormAssignment", "imported_paused"): TargetField(True, reason=_INERT),
    ("events.StageFormAssignment", "creation_operation_id"): TargetField(None, reason=_INERT),
    **{(label, name): TargetField(value, reason=_LEASE)
       for label in ("events.StageFormAsset", "payments.FinanceAttachment")
       for name, value in (("lease_token", None), ("lease_until", None), ("attempts", 0),
                           ("staging_version_id", ""), ("final_version_id", ""))},
}
