"""Strict wire types for this domain's optional loan-context API."""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from django.utils.translation import gettext

MAX_SAFE_INTEGER = 9007199254740991

class SafeInteger(serializers.Field):
    def __init__(self, *, minimum=0, **kwargs):
        self.minimum = minimum
        super().__init__(**kwargs)
        extend_schema_field({"type": "integer", "minimum": minimum, "maximum": MAX_SAFE_INTEGER})(self)

    def to_internal_value(self, value):
        if type(value) is not int or not self.minimum <= value <= MAX_SAFE_INTEGER:
            raise serializers.ValidationError(gettext("Expected a safe integer in the allowed range."))
        return value

    def to_representation(self, value):
        if type(value) is not int or not self.minimum <= value <= MAX_SAFE_INTEGER:
            raise serializers.ValidationError(gettext("Stored identifier exceeds the safe integer range."))
        return value

class ContextCAS(serializers.Serializer):
    expected_generation = serializers.UUIDField(format="hex_verbose")
    expected_revision = SafeInteger()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) != set(self.fields):
            raise serializers.ValidationError({"non_field_errors": [gettext("Unexpected or missing context fields.")]})
        return super().to_internal_value(data)

    def validate_expected_generation(self, value):
        raw = self.initial_data.get("expected_generation")
        if not isinstance(raw, str) or str(value) != raw or value.version != 4:
            raise serializers.ValidationError(gettext("Expected a canonical UUIDv4 generation."))
        return value
class BookingContextPut(ContextCAS):
    booking_id = SafeInteger(minimum=1)
