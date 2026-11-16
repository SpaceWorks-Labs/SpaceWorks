"""Account-merge dispositions for the L5 money, tax and finance-ledger models (release 2).

Money evidence (ledger entries, claims, maker-checker confirmations, opening balances) is
immutable history like ``payments.Payment``; settings and mutable attribution move.
"""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_HISTORY = "Immutable money evidence; actor_ids_for follows the alias."
_MUTABLE = "Mutable ownership or attribution; moves to the survivor."

ROWS = (
    (R, "payments.EventFinanceBudget", "set_by", _MUTABLE),
    (K, "payments.LedgerEntry", "created_by voided_by", _HISTORY),
    (R, "payments.MakerspaceTaxSettings", "updated_by", _MUTABLE),
    (K, "payments.OpeningBalance", "set_by", _HISTORY),
    (R, "payments.PaymentCaptureFlag", "resolved_by", _MUTABLE),
    (K, "payments.PaymentClaim", "claimant decided_by", _HISTORY),
    (R, "payments.PaymentPayLink", "created_by", _MUTABLE),
    (K, "payments.SettlementConfirmation", "decided_by proposed_by", _HISTORY),
)
