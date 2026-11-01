"""Release-2 lane L15: pricing, discounts, loan rental/damage/lost charges and fee waivers.

Entries expose ids, areas, components, modes and timings -- never a member's name, a
waiver reason or a staff note (both stay in the raw audit row for auditors)."""

from .presentation_catalog_types import P

ENTRIES = (
    P("pricing.override_set", "Item price set",
      ("domain", "component", "target_type", "target_id", "mode", "amount", "cap")),
    P("pricing.override_cleared", "Item price set back to the default",
      ("domain", "component", "target_type", "target_id")),
    P("pricing.discount_created", "Member discount created", ("discount_id", "plan_id", "via")),
    P("pricing.discount_updated", "Member discount changed", ("discount_id", "plan_id", "via")),
    P("pricing.discount_archived", "Member discount archived", ("discount_id", "via")),
    P("loan.rental_deferred", "Loan rental to be charged at return",
      ("request_id", "rental_timing"), request_refs=("request_id",)),
    P("loan.rental_raised", "Loan rental raised",
      ("request_id", "payment_id", "days", "timing", "discount_id"), request_refs=("request_id",)),
    P("loan.damage_charged", "Damage charge raised",
      ("request_id", "accountability_id", "payment_id", "evidence_id"), request_refs=("request_id",)),
    P("loan.lost_charged", "Lost item charge raised",
      ("request_id", "accountability_id", "payment_id", "evidence_id"), request_refs=("request_id",)),
    P("loan.accountability_not_charged", "Damage or loss recorded with no charge",
      ("request_id", "accountability_id"), request_refs=("request_id",)),
    P("loan.fee_waived", "Loan fees waived",
      ("request_id", "waiver_id", "components", "payment_ids", "refund_case_ids"), request_refs=("request_id",)),
    P("loan.fee_waiver_revoked", "Loan fee waiver revoked",
      ("request_id", "waiver_id", "revocation_id", "components"), request_refs=("request_id",)),
    P("booking.price_quoted_at_approval", "Booking charged at the approval-day price (no price frozen at request)"),
    P("charge.free_by_pricing", "Nothing charged (free under pricing)",
      ("subject_type", "subject_id", "domain", "outcome", "waiver_id", "discount_id")),
)
