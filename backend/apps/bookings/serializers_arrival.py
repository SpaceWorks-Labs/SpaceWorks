"""Allow-list projections deliberately independent from the roster serializer."""
from rest_framework import serializers
from .models import Booking


class BookingCredentialSerializer(serializers.Serializer):
    # Deliberately accept bounded strings: malformed/foreign/unknown all resolve 404.
    credential = serializers.CharField(max_length=128, trim_whitespace=False, write_only=True)

    def to_internal_value(self, data):
        from rest_framework.exceptions import NotFound
        if not isinstance(data, dict) or set(data) != {"credential"} or not isinstance(data.get("credential"), str):
            raise NotFound()
        if len(data["credential"]) > 128 or not data["credential"]:
            raise NotFound()
        return {"credential": data["credential"]}


class BookingArrivalSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    display_name = serializers.CharField()
    space_name = serializers.CharField()
    timezone = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=Booking.Status.choices)
    arrived_at = serializers.DateTimeField(allow_null=True)
    can_arrive = serializers.BooleanField()
    can_reverse = serializers.BooleanField()
    can_print_pass = serializers.BooleanField(read_only=True)
    departed_at = serializers.DateTimeField(allow_null=True, required=False)
    can_depart = serializers.BooleanField(required=False)
    waiver_state = serializers.ChoiceField(choices=("not_required", "current", "missing"))


class BookingConfirmationSerializer(serializers.Serializer):
    public_token = serializers.UUIDField()
    space_name = serializers.CharField()
    timezone = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.ChoiceField(choices=Booking.Status.choices)
    location = serializers.CharField()
    description = serializers.CharField()
    arrived_at = serializers.DateTimeField(allow_null=True)
    can_cancel = serializers.BooleanField()
    cancellation_cutoff_at = serializers.DateTimeField()
    pass_available = serializers.BooleanField(read_only=True)
    qr_value = serializers.CharField(allow_null=True)
    google_calendar_url = serializers.URLField()
