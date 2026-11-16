"""Decision 223 (guest passes): tenant-dump field snapshot, authority and uniqueness.

Passes, products and the guest policy travel with the space (data_export `classification_guest_passes`);
foreign keys remap like any other. A live pass confers nothing the target space does not already allow: it
is bounded by its window, the target's own `membership.guest_passes` switch and a holder account that must
exist there. The frozen entitlements are the pass's own history, and the idempotency key (`operation_id`) is
kept so a replayed request on the target cannot double-issue. The Payment rows of paid day passes travel with
the payments ledger, which resolves its `guest_pass` subject through `PAYMENT_SUBJECT_REFERENCES`.
"""
from apps.data_export.classification_guest_passes import FIELDS as _FIELDS

FIELD_NAMES = {label: frozenset(names.split()) for label, names in _FIELDS.items()}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("makerspaces.GuestPass", "kind status valid_from valid_until pass_date entitlements waiver_version "
              "waiver_accepted_at revoked_at revoked_reason operation_id created_at", keep,
              "A pass is the holder's dated permit and its history; the target's own switches and the holder's "
              "account still decide whether it unlocks anything."),
        *same("makerspaces.DayPassProduct", "name amount currency entitlements daily_cap is_public is_active "
              "archived_at", keep, "Day-pass products are the space's own priced offers."),
        *same("makerspaces.GuestPassPolicy", "guest_borrowing_mode guest_machine_mode sponsored_liability "
              "walk_in_registration_creates waiver_required_on_site waiver_gate_without_passes sponsor_min_tenure_days "
              "max_concurrent_guests_per_sponsor sponsor_must_be_present visits_before_join_prompt "
              "hard_visit_cap day_pass_daily_cap", keep,
              "The guest policy is the Space Manager's own configuration; the target's modules still gate it."),
    )


def unique_rules(remap, policy):
    """None: every guest-pass uniqueness is scoped by the space (or its holder), which the guard treats as tenant-owned."""
    return {}
