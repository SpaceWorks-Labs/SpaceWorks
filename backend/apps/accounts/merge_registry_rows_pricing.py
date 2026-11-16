"""Account-merge dispositions for the L15 pricing kernel models (release 2)."""

from .merge_registry_types import KEEP_ON_SHELL as K, REPOINT as R

_MUTABLE = "Mutable ownership or attribution; moves to the survivor."

ROWS = (
    (K, "payments.LoanFeeWaiver", "created_by", "Append-only waiver evidence (DB-guarded); actor_ids_for follows the alias."),
    (R, "payments.PriceDiscount", "created_by", _MUTABLE),
    (R, "payments.PriceDiscount", "member", "A one-member discount follows the person to the survivor."),
    (R, "payments.PriceOverride", "updated_by", _MUTABLE),
    (R, "payments.PricingDefault", "updated_by", _MUTABLE),
)
