"""Release-2 lane L15: pricing, discounts, loan rental/damage/lost charges and fee waivers.

Entries expose ids, areas, components, modes and timings -- never a member's name, a
waiver reason or a staff note (both stay in the raw audit row for auditors)."""

from django.utils.translation import gettext_noop
from .presentation_catalog_types import P

ENTRIES = (
    P("pricing.override_set", gettext_noop("Item price set"),
      ("domain", "component", "target_type", "target_id", "mode", "amount", "cap")),
    P("pricing.override_cleared", gettext_noop("Item price set back to the default"),
      ("domain", "component", "target_type", "target_id")),
    P("pricing.discount_created", gettext_noop("Member discount created"), ("discount_id", "plan_id", "via")),
    P("pricing.discount_updated", gettext_noop("Member discount changed"), ("discount_id", "plan_id", "via")),
    P("pricing.discount_archived", gettext_noop("Member discount archived"), ("discount_id", "via")),
    P("loan.rental_deferred", gettext_noop("Loan rental to be charged at return"),
      ("request_id", "rental_timing"), request_refs=("request_id",)),
    P("loan.rental_raised", gettext_noop("Loan rental raised"),
      ("request_id", "payment_id", "days", "timing", "discount_id"), request_refs=("request_id",)),
    P("loan.damage_charged", gettext_noop("Damage charge raised"),
      ("request_id", "accountability_id", "payment_id", "evidence_id"), request_refs=("request_id",)),
    P("loan.lost_charged", gettext_noop("Lost item charge raised"),
      ("request_id", "accountability_id", "payment_id", "evidence_id"), request_refs=("request_id",)),
    P("loan.accountability_not_charged", gettext_noop("Damage or loss recorded with no charge"),
      ("request_id", "accountability_id"), request_refs=("request_id",)),
    P("loan.fee_waived", gettext_noop("Loan fees waived"),
      ("request_id", "waiver_id", "components", "payment_ids", "refund_case_ids"), request_refs=("request_id",)),
    P("loan.fee_waiver_revoked", gettext_noop("Loan fee waiver revoked"),
      ("request_id", "waiver_id", "revocation_id", "components"), request_refs=("request_id",)),
    P("booking.price_quoted_at_approval", gettext_noop("Booking charged at the approval-day price (no price frozen at request)")),
    P("charge.free_by_pricing", gettext_noop("Nothing charged (free under pricing)"),
      ("subject_type", "subject_id", "domain", "outcome", "waiver_id", "discount_id")),
)
