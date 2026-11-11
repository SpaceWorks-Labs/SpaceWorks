"""Tax settings, GSTIN check and the sample-invoice preview (lane L5)."""

from decimal import Decimal

from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.payments.models import MakerspaceTaxSettings
from apps.payments.tax.gstin import STATE_NAMES


class TaxSettingsSerializer(serializers.ModelSerializer):
    enabled = serializers.SerializerMethodField(help_text="Whether the billing.tax capability is on for the space.")
    rate_bps = serializers.IntegerField(min_value=0, max_value=10000, required=False)

    class Meta:
        model = MakerspaceTaxSettings
        fields = ("enabled", "mode", "tax_name", "rate_bps", "prices_include_tax", "gstin", "state_code", "scheme",
                  "exempt", "sac_code", "foreign_currency", "lut_number", "invoice_prefix", "credit_note_prefix",
                  "updated_at")
        read_only_fields = ("enabled", "updated_at")

    def get_enabled(self, policy) -> bool:
        from apps.makerspaces.platform import feature_enabled
        return feature_enabled(policy.makerspace, "billing.tax")


class TaxValidationErrorSerializer(serializers.Serializer):
    detail = serializers.CharField(required=False)
    code = serializers.CharField(required=False)
    gstin = serializers.ListField(child=serializers.CharField(), required=False)
    state_code = serializers.ListField(child=serializers.CharField(), required=False)
    tax_name = serializers.ListField(child=serializers.CharField(), required=False)
    lut_number = serializers.ListField(child=serializers.CharField(), required=False)
    sac_code = serializers.ListField(child=serializers.CharField(), required=False)
    invoice_prefix = serializers.ListField(child=serializers.CharField(), required=False)
    credit_note_prefix = serializers.ListField(child=serializers.CharField(), required=False)


class GstinCheckSerializer(serializers.Serializer):
    gstin = serializers.CharField(max_length=32)


class GstinResultSerializer(serializers.Serializer):
    valid = serializers.BooleanField()
    gstin = serializers.CharField()
    state_code = serializers.CharField()
    state_name = serializers.CharField()


class TaxPreviewRequestSerializer(serializers.Serializer):
    amount = MoneyField(max_digits=13, decimal_places=3, min_value=Decimal("0.001"))
    currency = serializers.RegexField(r"^[a-zA-Z]{3}$", required=False)
    recipient_state = serializers.ChoiceField(choices=sorted(STATE_NAMES), required=False, allow_blank=True)
    settings = TaxSettingsSerializer(required=False, help_text="Unsaved settings to preview; defaults to saved ones.")


class TaxComponentSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    rate_bps = serializers.IntegerField()
    amount = MoneyField(max_digits=13, decimal_places=3)


class TaxPreviewSerializer(serializers.Serializer):
    title = serializers.CharField()
    currency = serializers.CharField()
    entered_amount = MoneyField(max_digits=13, decimal_places=3)
    taxable = MoneyField(max_digits=13, decimal_places=3)
    tax = MoneyField(max_digits=13, decimal_places=3)
    gross = MoneyField(max_digits=13, decimal_places=3)
    supply_type = serializers.CharField()
    place_of_supply = serializers.CharField(allow_blank=True)
    components = TaxComponentSerializer(many=True)
    notes = serializers.ListField(child=serializers.CharField())
    sample_number = serializers.CharField()
