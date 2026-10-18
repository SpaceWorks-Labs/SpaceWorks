"""Closed line evidence; F's reusable money/itinerary rules remain authoritative."""
from rest_framework import serializers
from .serializers_request import ClosedSerializer, StrictInteger, Currency
from apps.payments.event_payouts.validation import MAX_MINOR


class ReceiptReference(ClosedSerializer):
    asset_id = StrictInteger(min_value=1)
    generation = StrictInteger(min_value=1)
    sha256 = serializers.RegexField(r"^[a-f0-9]{64}$")
    receipt_total_minor = StrictInteger(min_value=1, max_value=MAX_MINOR)


class ClaimLineInput(ClosedSerializer):
    line_uuid = serializers.UUIDField()
    category = serializers.ChoiceField(choices=("rail", "air", "bus", "ground_transport", "lodging"))
    vendor = serializers.CharField(max_length=500)
    description = serializers.CharField(max_length=2000)
    traveller = serializers.CharField(max_length=200)
    expense_date = serializers.DateField()
    original_amount_minor = StrictInteger(min_value=1, max_value=MAX_MINOR)
    original_currency = Currency()
    fx_rate = serializers.RegexField(r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,12})?$")
    rate_date = serializers.DateField()
    rate_source = serializers.ChoiceField(choices=("manual", "receipt"))
    source_note = serializers.CharField(max_length=500, allow_blank=True, default="")
    receipt = ReceiptReference()
    route = serializers.DictField(default=dict)
    lodging_starts_on = serializers.DateField(required=False)
    lodging_ends_on = serializers.DateField(required=False)
    lodging_nights = StrictInteger(min_value=1, max_value=365, required=False)


class ClaimDraftInput(ClosedSerializer):
    lines = ClaimLineInput(many=True, allow_empty=True, max_length=50)

    def validate_lines(self, value):
        identities = [row["line_uuid"] for row in value]
        if len(identities) != len(set(identities)):
            raise serializers.ValidationError("Line identifiers must be unique.")
        return value
