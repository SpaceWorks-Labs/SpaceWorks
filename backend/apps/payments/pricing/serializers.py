"""Pricing API shapes: the quote, a domain's rate card, and the impact preview (lane L15)."""

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.payments.models_pricing import PricingDefault, PricingDomain


class PricingQuoteLineSerializer(serializers.Serializer):
    component = serializers.CharField()
    label = serializers.CharField()
    subject_type = serializers.CharField(allow_null=True)
    quantity = serializers.DecimalField(max_digits=16, decimal_places=4)
    unit_amount = MoneyField(max_digits=13, decimal_places=3)
    gross = MoneyField(max_digits=13, decimal_places=3)
    discount = MoneyField(max_digits=13, decimal_places=3)
    net = MoneyField(max_digits=13, decimal_places=3)
    source = serializers.CharField()
    cap_applied = serializers.BooleanField()
    target = serializers.JSONField(allow_null=True)
    detail = serializers.JSONField()


class PricingQuoteDiscountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    audience = serializers.CharField()
    saving = MoneyField(max_digits=13, decimal_places=3)


class PricingQuoteSerializer(serializers.Serializer):
    domain = serializers.CharField()
    currency = serializers.CharField()
    mode = serializers.CharField()
    lines = PricingQuoteLineSerializer(many=True)
    subtotal = MoneyField(max_digits=13, decimal_places=3)
    discount_total = MoneyField(max_digits=13, decimal_places=3)
    total = MoneyField(max_digits=13, decimal_places=3)
    discount = PricingQuoteDiscountSerializer(allow_null=True)
    waiver = serializers.JSONField(allow_null=True)
    notes = serializers.ListField(child=serializers.CharField())
    digest = serializers.CharField()
    # Decision 221(d): plan included hours applied to a booking quote (absent otherwise).
    included_hours = serializers.JSONField(required=False, allow_null=True)


def quote_payload(quote):
    data = quote.as_json()
    data.pop("version", None)
    data.pop("promo", None)
    return data


class PricingRateLineSerializer(serializers.Serializer):
    component = serializers.CharField()
    label = serializers.CharField(read_only=True)
    unit = serializers.CharField(read_only=True)
    has_cap = serializers.BooleanField(read_only=True)
    has_grace = serializers.BooleanField(read_only=True)
    has_increment = serializers.BooleanField(read_only=True)
    has_minimum = serializers.BooleanField(read_only=True)
    discountable = serializers.BooleanField(read_only=True)
    staff_set = serializers.BooleanField(read_only=True)
    prefill_only = serializers.BooleanField(read_only=True)
    read_only = serializers.BooleanField(read_only=True)
    amount = MoneyField(max_digits=13, decimal_places=3, min_value=0)
    cap = MoneyField(max_digits=13, decimal_places=3, min_value=0, allow_null=True, required=False)
    grace_units = serializers.IntegerField(min_value=0, max_value=365, required=False)
    billing_increment = serializers.IntegerField(min_value=0, max_value=1440, required=False)
    minimum = serializers.IntegerField(min_value=0, max_value=1440, required=False)
    source = serializers.CharField(read_only=True)


class PricingLendingSerializer(serializers.Serializer):
    deposit_mode = serializers.ChoiceField(choices=["none", "fixed", "per_product"], required=False)
    deposit_amount = MoneyField(max_digits=13, decimal_places=3, min_value=0, required=False)
    deposit_blocks_issue = serializers.BooleanField(required=False)
    late_per_day = MoneyField(max_digits=13, decimal_places=3, min_value=0, required=False)
    late_cap = MoneyField(max_digits=13, decimal_places=3, min_value=0, required=False)
    grace_days = serializers.IntegerField(min_value=0, max_value=365, required=False)


class PricingDefaultSerializer(serializers.Serializer):
    domain = serializers.ChoiceField(choices=PricingDomain.choices)
    label = serializers.CharField()
    enabled = serializers.BooleanField(help_text="The charges.pricing capability.")
    currency = serializers.CharField()
    mode = serializers.ChoiceField(choices=PricingDefault.Mode.choices)
    stored = serializers.BooleanField(help_text="False until a Space Manager saves this area once.")
    editable = serializers.BooleanField()
    via = serializers.CharField(allow_null=True)
    locked = serializers.BooleanField()
    refusal = serializers.CharField(allow_null=True)
    rental_timing = serializers.ChoiceField(choices=PricingDefault.RentalTiming.choices, allow_null=True)
    rental_timing_editable = serializers.BooleanField()
    failed_job_charge = serializers.ChoiceField(choices=PricingDefault.FailedJobCharge.choices, allow_null=True)
    lines = PricingRateLineSerializer(many=True)
    lending = PricingLendingSerializer(allow_null=True)


class PricingDefaultWriteSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=PricingDefault.Mode.choices, required=False)
    lines = PricingRateLineSerializer(many=True, required=False)
    lending = PricingLendingSerializer(required=False)
    failed_job_charge = serializers.ChoiceField(choices=PricingDefault.FailedJobCharge.choices, required=False)


class RentalTimingSerializer(serializers.Serializer):
    rental_timing = serializers.ChoiceField(choices=PricingDefault.RentalTiming.choices)
    editable = serializers.BooleanField(read_only=True)
    via = serializers.CharField(read_only=True, allow_null=True)
    locked = serializers.BooleanField(read_only=True)


class PricingImpactChangeSerializer(serializers.Serializer):
    target_type = serializers.CharField()
    target_id = serializers.IntegerField()
    label = serializers.CharField()
    component = serializers.CharField()
    before = MoneyField(max_digits=13, decimal_places=3)
    after = MoneyField(max_digits=13, decimal_places=3)
    source = serializers.CharField()


class PricingImpactSerializer(serializers.Serializer):
    domain = serializers.CharField()
    currency = serializers.CharField()
    items_checked = serializers.IntegerField()
    changed = serializers.IntegerField()
    truncated = serializers.BooleanField()
    changes = PricingImpactChangeSerializer(many=True)


class PricingCurrencySerializer(serializers.Serializer):
    default_currency = serializers.RegexField(r"^[A-Za-z]{3}$", max_length=3)
