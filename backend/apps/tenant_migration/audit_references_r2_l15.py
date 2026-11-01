"""Release-2 lane L15 audit meta ids. Pricing rows, waivers, loans and their charges travel
with the space, so their ids remap; a polymorphic item or subject id stays provenance."""

from .audit_references_targets import AuditReference, AuditReferenceDisposition

R = AuditReferenceDisposition.REMAP
S = AuditReferenceDisposition.SOURCE_LOCAL_SNAPSHOT
_S = AuditReference(S, None, "programme_source_provenance")


def _remap(model, *pairs):
    return {pair: AuditReference(R, model) for pair in pairs}


_LOAN_CHARGES = ("loan.rental_raised", "loan.damage_charged", "loan.lost_charged")

EDGES = {
    **_remap("hardware_requests.HardwareRequest",
             *((action, "request_id") for action in (*_LOAN_CHARGES, "loan.rental_deferred", "loan.fee_waived",
                                                     "loan.fee_waiver_revoked", "loan.accountability_not_charged"))),
    **_remap("payments.Payment", *((action, "payment_id") for action in _LOAN_CHARGES),
             ("loan.fee_waived", "payment_ids")),
    **_remap("hardware_requests.RequesterAccountability", ("loan.damage_charged", "accountability_id"),
             ("loan.lost_charged", "accountability_id"), ("loan.accountability_not_charged", "accountability_id")),
    **_remap("evidence.EvidencePhoto", ("loan.damage_charged", "evidence_id"), ("loan.lost_charged", "evidence_id")),
    **_remap("payments.RefundCase", ("loan.fee_waived", "refund_case_ids")),
    **_remap("payments.LoanFeeWaiver", ("loan.fee_waived", "waiver_id"), ("loan.fee_waiver_revoked", "waiver_id"),
             ("loan.fee_waiver_revoked", "revocation_id"), ("charge.free_by_pricing", "waiver_id")),
    **_remap("payments.PriceDiscount", ("pricing.discount_created", "discount_id"),
             ("pricing.discount_updated", "discount_id"), ("pricing.discount_archived", "discount_id"),
             ("loan.rental_raised", "discount_id"), ("charge.free_by_pricing", "discount_id"),
             ("payment.created", "discount_id")),
    **_remap("makerspaces.MembershipPlan", ("pricing.discount_created", "plan_id"),
             ("pricing.discount_updated", "plan_id")),
    ("booking.price_quoted_at_approval", "booking_id"): AuditReference(R, "bookings.Booking"),
    ("pricing.discount_created", "member_id"): AuditReference(S, "accounts.User"),
    ("pricing.discount_updated", "member_id"): AuditReference(S, "accounts.User"),
    ("pricing.override_set", "target_id"): _S,
    ("pricing.override_cleared", "target_id"): _S,
    ("charge.free_by_pricing", "subject_id"): _S,
}
