"""Release-2 lane L15 (paid and free everywhere): tenant-dump field snapshot and authority.

Every pricing row travels with the space it configures (data_export
`classification_r2_l15`). A per-item price names its item through one of four foreign
keys, which remap like any other; waivers remap their loan. `Payment.pricing_snapshot` is frozen history and travels unchanged -- the
ids inside it are source-local snapshots of what the charge was priced from.
"""

FIELD_NAMES = {
    "payments.PricingDefault": frozenset(
        "id makerspace domain mode rental_timing failed_job_charge updated_by updated_at".split()),
    "payments.PricingDefaultLine": frozenset(
        "id default component amount cap grace_units billing_increment minimum".split()),
    "payments.PriceOverride": frozenset(
        "id makerspace domain component target_type product machine pool room mode amount cap updated_by "
        "updated_at".split()),
    "payments.PriceDiscount": frozenset(
        "id makerspace name audience plan member domains components percent_bps amount_off starts_at ends_at "
        "is_active archived_at created_by created_at updated_at".split()),
    "payments.LoanFeeWaiver": frozenset(
        "id makerspace request components reason revokes created_by created_at".split()),
}
EXTRA_FIELDS = {
    "payments.Payment": frozenset({"pricing_snapshot"}),
    "bookings.Booking": frozenset({"pricing_snapshot"}),
}
PROJECTED_LABELS = frozenset(FIELD_NAMES)


def authority_entries(authority, disposition):
    def same(label, names, chosen, reason):
        return tuple(((label, name), authority(chosen, reason)) for name in names.split())

    keep = disposition.PRESERVE
    return (
        *same("payments.Payment", "pricing_snapshot", keep,
              "The frozen quote is the charge's own history; never recomputed."),
        *same("bookings.Booking", "pricing_snapshot", keep,
              "The price quoted when the booking was requested; approval charges exactly this (#159)."),
        *same("payments.PricingDefault", "domain mode rental_timing failed_job_charge updated_at", keep,
              "A rate card is the space's own pricing configuration."),
        *same("payments.PricingDefaultLine", "component amount cap grace_units billing_increment minimum", keep,
              "Rates, caps and billing increments are the space's own configuration."),
        *same("payments.PriceOverride", "domain component target_type mode amount cap updated_at", keep,
              "An item's price is the space's own configuration."),
        *same("payments.PriceDiscount", "name audience domains components percent_bps amount_off starts_at "
              "ends_at is_active archived_at created_at updated_at", keep,
              "Discount rules are the space's own money policy."),
        *same("payments.LoanFeeWaiver", "components reason created_at", keep,
              "A fee waiver is the append-only record of a staff decision on a loan."),
    )
