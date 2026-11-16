"""Decision 223 (guest passes): literal export classification.

A guest pass is a dated permit on an existing account, never a membership, so it exports with
the space as history: who held it, its kind, window, status, the frozen entitlements snapshot, the
waiver stamp (version and time only, never the waiver body), the sponsor and the issuer. The holder is
the pass's data subject (subject export); the sponsor, issuer and reviser are relational account
references. Day-pass products and the per-space guest policy are tenant configuration. The `Payment`
rows of paid day passes are exported by the payments ledger, which is permanently core.
"""
from .types import TenantPredicate as P

FIELDS = {
    "makerspaces.GuestPass": "id makerspace holder kind status valid_from valid_until pass_date sponsor "
                             "sponsor_membership product entitlements accepted_waiver waiver_version "
                             "waiver_accepted_at issued_by revoked_by revoked_at revoked_reason "
                             "converted_membership operation_id created_at",
    "makerspaces.DayPassProduct": "id makerspace name amount currency entitlements daily_cap is_public is_active "
                                  "archived_at created_at updated_at",
    "makerspaces.GuestPassPolicy": "id makerspace guest_borrowing_mode guest_machine_mode sponsored_liability "
                                   "walk_in_registration_creates waiver_required_on_site waiver_gate_without_passes sponsor_min_tenure_days "
                                   "max_concurrent_guests_per_sponsor sponsor_must_be_present "
                                   "visits_before_join_prompt hard_visit_cap day_pass_daily_cap updated_by updated_at",
}
DATASETS = {
    "makerspaces.GuestPass": ("members/guest_passes.csv", P(("makerspace",))),
    "makerspaces.DayPassProduct": ("members/day_pass_products.csv", P(("makerspace",))),
    "makerspaces.GuestPassPolicy": ("members/guest_pass_policy.csv", P(("makerspace",))),
}
SUBJECT_PATHS = {"makerspaces.GuestPass": ("holder",)}
RELATIONAL_USER_FIELDS = frozenset({
    ("makerspaces.GuestPass", "holder"),
    ("makerspaces.GuestPass", "sponsor"),
    ("makerspaces.GuestPass", "issued_by"),
    ("makerspaces.GuestPass", "revoked_by"),
    ("makerspaces.GuestPassPolicy", "updated_by"),
})
# Fixed enum strings (`presence`, `borrow`, `machines`), never ids.
NON_REFERENCE_JSON_FIELDS = frozenset({
    ("makerspaces.GuestPass", "entitlements"),
    ("makerspaces.DayPassProduct", "entitlements"),
})
