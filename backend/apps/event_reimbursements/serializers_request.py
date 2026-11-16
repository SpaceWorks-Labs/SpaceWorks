"""Closed application-time request block shared by both canonical submit bridges."""
from django.utils.translation import gettext
from decimal import Decimal
from rest_framework import serializers
from apps.payments.currencies import normalize_supported_currency
from apps.payments.event_payouts.validation import MAX_MINOR

ESTIMATE_MAX_MINOR = 10_000_000  # G1 fixed request-form money bound.


class ClosedSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError({"code": "invalid_fields"})
        return super().to_internal_value(data)


class StrictInteger(serializers.IntegerField):
    def to_internal_value(self, value):
        if type(value) is not int:
            self.fail("invalid")
        return super().to_internal_value(value)


class Currency(serializers.CharField):
    def to_internal_value(self, value):
        try:
            return normalize_supported_currency(value)
        except ValueError:
            raise serializers.ValidationError(gettext("Unsupported currency.")) from None


class FormDescriptor(ClosedSerializer):
    schema_version = StrictInteger(min_value=2, max_value=2)
    form_id = serializers.CharField(max_length=100)
    revision = StrictInteger(min_value=1)


class Estimate(ClosedSerializer):
    category = serializers.ChoiceField(choices=("rail", "air", "bus", "ground_transport", "lodging"))
    amount_minor = StrictInteger(min_value=1, max_value=ESTIMATE_MAX_MINOR)
    currency = Currency()


class ReimbursementRequestSubmissionSerializer(ClosedSerializer):
    submit = serializers.BooleanField()
    programme_id = StrictInteger(min_value=1)
    programme_version = StrictInteger(min_value=1)
    form = FormDescriptor()
    estimates = Estimate(many=True, allow_empty=False, max_length=5)
    itinerary = serializers.DictField()
    need_statement = serializers.CharField(max_length=5000, trim_whitespace=True, allow_blank=False)
    distance_km = serializers.RegexField(r"^(?:0|[1-9][0-9]{0,4})(?:\.[0-9]{1,3})?$", required=False)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or data.get("submit") is not True:
            raise serializers.ValidationError({"code": "reimbursement_consent_required"})
        return super().to_internal_value(data)

    def validate(self, value):
        categories = [row["category"] for row in value["estimates"]]
        if len(categories) != len(set(categories)) or sum(row["amount_minor"] for row in value["estimates"]) > MAX_MINOR:
            raise serializers.ValidationError({"code": "invalid_estimates"})
        if "distance_km" in value and Decimal(value["distance_km"]) > 40075:
            raise serializers.ValidationError({"code": "invalid_distance"})
        return value
