"""Release-2 lane L15 (paid and free everywhere): literal export classification.

Every L15 row is the space's own pricing configuration or loan decision and exports with
the space: rate cards and their lines, per-item overrides (one of four item foreign
keys), member discount rules, and loan fee waivers. A member-specific
discount names that member (a relational account reference); a waiver's reason is
staff-authored financial context, shown to staff only. New column:
`Payment.pricing_snapshot`, the frozen net quote a charge was raised from (prices,
components, item labels, discount and waiver ids -- no account or contact data).
"""

from .types import TenantPredicate as P

EXPORTED_FIELDS = {
    "payments.PricingDefault": "id makerspace domain mode rental_timing failed_job_charge updated_by updated_at",
    "payments.PricingDefaultLine": "id default component amount cap grace_units billing_increment minimum",
    "payments.PriceOverride": "id makerspace domain component target_type product machine pool room mode amount cap "
                              "updated_by updated_at",
    "payments.PriceDiscount": "id makerspace name audience plan member domains components percent_bps amount_off "
                              "starts_at ends_at is_active archived_at created_by created_at updated_at",
    "payments.LoanFeeWaiver": "id makerspace request components reason revokes created_by created_at",
}
EXTRA_FIELDS = {
    "payments.Payment": "pricing_snapshot",
}
DATASET_SPECS = {
    "payments.PricingDefault": ("payments/pricing_defaults.csv", P(("makerspace",))),
    "payments.PricingDefaultLine": ("payments/pricing_default_lines.csv", P(("default__makerspace",))),
    "payments.PriceOverride": ("payments/price_overrides.csv", P(("makerspace",))),
    "payments.PriceDiscount": ("payments/price_discounts.csv", P(("makerspace",))),
    "payments.LoanFeeWaiver": ("payments/loan_fee_waivers.csv", P(("makerspace",))),
}
RELATIONAL_USER_FIELDS = frozenset({
    ("payments.PricingDefault", "updated_by"),
    ("payments.PriceOverride", "updated_by"),
    ("payments.PriceDiscount", "member"),
    ("payments.PriceDiscount", "created_by"),
    ("payments.LoanFeeWaiver", "created_by"),
})
# Discount scopes and frozen quotes: area and component names, prices, rule/waiver ids.
JSON_FIELDS = frozenset({
    ("payments.Payment", "pricing_snapshot"),
    ("payments.PriceDiscount", "domains"),
    ("payments.PriceDiscount", "components"),
    ("payments.LoanFeeWaiver", "components"),
})


def extend(fields):
    fields.update(EXPORTED_FIELDS)
    for label, extra in EXTRA_FIELDS.items():
        fields[label] += " " + extra
    return fields
