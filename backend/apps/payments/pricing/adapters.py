"""Legacy storage, read and written through the rate card (lane L15, no data migration).

The release-1 price fields stay the source of truth for what they already hold:

* lending: `MakerspacePaymentSettings.loan_deposit_mode/_amount` (the deposit) and
  `loan_late_fee_per_day/_cap`, `loan_grace_days` (the late fee) -- the space defaults;
* an item's own price field (`InventoryProduct.deposit_amount`, `BookableSpace.payment_amount`)
  -- read by the domain builders as the item's custom price;
* membership: `MembershipPlan.amount` and `MakerspaceMembershipSettings.joining_fee`
  (read-only here: lane L4 owns plans).

The `payment-settings` loan fields and `machine-type-pricing` stay as aliases for clients
that already write them, so both paths edit the same columns.
"""

from decimal import Decimal

from apps.payments.pricing.rates import NONE, Rate

LOAN_LEGACY_COMPONENTS = ("deposit", "late_per_day")


def legacy_defaults(card):
    if card.domain == "loans":
        return _loan_defaults(card.payment_settings)
    if card.domain == "membership":
        return _membership_defaults(card.makerspace)
    return {}


def _loan_defaults(settings_row):
    from apps.payments.models import MakerspacePaymentSettings

    rates = {}
    if settings_row.loan_deposit_mode == MakerspacePaymentSettings.LoanDepositMode.FIXED:
        rates["deposit"] = Rate(amount=Decimal(settings_row.loan_deposit_amount or 0), source="default")
    cap = Decimal(settings_row.loan_late_fee_cap or 0)
    rates["late_per_day"] = Rate(amount=Decimal(settings_row.loan_late_fee_per_day or 0), source="default",
                                 cap=cap if cap > 0 else None, grace=settings_row.loan_grace_days or 0)
    return rates


def _membership_defaults(makerspace):
    from apps.makerspaces.models import MakerspaceMembershipSettings

    row = MakerspaceMembershipSettings.objects.filter(makerspace=makerspace).first()
    fee = Decimal(getattr(row, "joining_fee", 0) or 0)
    dues = Decimal(getattr(makerspace, "membership_dues_amount", 0) or 0)
    return {"joining_fee": Rate(amount=fee, source="default") if fee > 0 else NONE,
            "dues": Rate(amount=dues, source="default") if dues > 0 else NONE}


def deposit_mode(card):
    return card.payment_settings.loan_deposit_mode


def loan_legacy_values(settings_row):
    """The lending default block as the pricing screen shows it."""
    return {
        "deposit_mode": settings_row.loan_deposit_mode,
        "deposit_amount": settings_row.loan_deposit_amount,
        "deposit_blocks_issue": settings_row.loan_deposit_blocks_issue,
        "late_per_day": settings_row.loan_late_fee_per_day,
        "late_cap": settings_row.loan_late_fee_cap,
        "grace_days": settings_row.loan_grace_days,
    }


LOAN_FIELD_MAP = {
    "deposit_mode": "loan_deposit_mode",
    "deposit_amount": "loan_deposit_amount",
    "deposit_blocks_issue": "loan_deposit_blocks_issue",
    "late_per_day": "loan_late_fee_per_day",
    "late_cap": "loan_late_fee_cap",
    "grace_days": "loan_grace_days",
}


def write_loan_legacy(makerspace, values):
    """Write the lending block into `MakerspacePaymentSettings` (the alias the rail endpoint edits).

    Returns `(before, after)` dicts of the fields that changed. The caller holds the
    makerspace lock and audits.
    """
    from apps.payments.models import MakerspacePaymentSettings

    settings_row, _ = MakerspacePaymentSettings.objects.select_for_update().get_or_create(makerspace=makerspace)
    before, after = {}, {}
    for key, column in LOAN_FIELD_MAP.items():
        if key not in values:
            continue
        old = getattr(settings_row, column)
        if old != values[key]:
            before[key], after[key] = str(old), str(values[key])
            setattr(settings_row, column, values[key])
    if after:
        settings_row.save()  # save() runs full_clean: currency and non-negative amounts
    return before, after
