"""Strict inputs for edits, moves and resource duplication."""

from rest_framework import serializers


class StrictInputSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError({key: "Unexpected field." for key in sorted(set(data) - set(self.fields))})
        return super().to_internal_value(data)


class BookingDetailsInputSerializer(StrictInputSerializer):
    note = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    custom_answers = serializers.JSONField(allow_null=True, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("Provide a note or custom answers.")
        return attrs


class BookingTimeInputSerializer(StrictInputSerializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs["ends_at"] <= attrs["starts_at"]:
            raise serializers.ValidationError({"ends_at": "End time must be after start time."})
        return attrs


class BookingCloneInputSerializer(StrictInputSerializer):
    copy_booking_rules = serializers.BooleanField(default=False, required=False)
