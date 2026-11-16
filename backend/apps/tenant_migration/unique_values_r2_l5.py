"""Deployment-global uniqueness for lane L5's money rows.

Most L5 uniqueness is tenant-scoped (a claim reference is unique per space, an FY
counter per space and series) and needs no rule. The rows below follow a remapped parent
exactly once, except a provider dispute id, which is the provider's own identifier and
travels verbatim: a target collision means the same dispute is already recorded there, and
the import refuses with `dispute_conflict` rather than recording it twice.
"""

from .insertion_errors import ArchiveFormatError
from .unique_values_policy import PRESERVE, REMAP, _policy


def _dispute_conflict(row, target, value):
    raise ArchiveFormatError(
        f"dispute_conflict: provider dispute {value!r} is already recorded on the target; "
        "the same space appears to be imported twice.")


_dispute_conflict.refuses_collision = True

RULES = {
    ("payments.LedgerEntry", "ledger_entry_receipt_once"): _policy(
        REMAP, "A receipt photo backs one entry; follows the imported evidence row."),
    ("payments.PaymentCaptureFlag", "capture_flag_once"): _policy(
        REMAP, "One flag per capture and kind; follows the imported payment."),
    ("payments.PaymentClaim", "payment_claim_one_open"): _policy(
        REMAP, "One open claim per charge; follows the imported payment."),
    ("payments.SettlementConfirmation", "field:settlement"): _policy(
        REMAP, "A confirmation writes one receipt; follows the imported settlement."),
    ("payments.PaymentDispute", "dispute_once_per_provider"): _policy(
        PRESERVE, "Provider dispute ids travel verbatim; a target collision refuses the import.",
        field="provider_dispute_id", generator=_dispute_conflict),
}
