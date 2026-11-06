"""Account-merge dispositions for lane r2-idcards-best certificate signatories (#199)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_SIGNATORY = ("The account that approves designs for a signatory slot follows the surviving account, so a "
              "merged person keeps approving their own signature.")
_APPROVAL = "Append-only attribution of an approval; stays with the account that approved."

ROWS = (
    (R, "events.EventCertificateSignatory", "member", _SIGNATORY),
    (K, "events.EventCertificateSignatoryApproval", "approved_by", _APPROVAL),
)
