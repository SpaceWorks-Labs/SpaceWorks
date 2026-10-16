"""Resource metadata and dedicated booking-rule write contracts."""

from rest_framework import serializers

from apps.bookings.exceptions import BookerNamesRequiresAvailability
from apps.bookings.models import BookableSpace
from apps.forms_schema.serializers import CustomFormSchemaField


class BookableSpaceWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    kind = serializers.ChoiceField(
        choices=BookableSpace.Kind.choices,
        default=BookableSpace.Kind.OTHER,
        required=False,
    )
    description = serializers.CharField(allow_blank=True, default='', required=False)
    capacity = serializers.IntegerField(default=0, min_value=0, required=False)
    location = serializers.CharField(
        allow_blank=True,
        default='',
        max_length=255,
        required=False,
    )
    is_public = serializers.BooleanField(default=False, required=False)
    show_public_availability = serializers.BooleanField(default=False, required=False)
    show_public_booker_names = serializers.BooleanField(default=False, required=False)
    # approval_mode is a booking rule; it is writable ONLY through the dedicated
    # MANAGE_BOOKINGS booking-rules endpoint, never this MANAGE_BOOKINGS path.
    custom_form = CustomFormSchemaField(
        allow_null=True,
        required=False,
    )
    requester_notifications_enabled = serializers.BooleanField(
        allow_null=True,
        default=None,
        required=False,
    )
    payment_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        default=0,
        required=False,
    )
    # The machine type this space is booked to use; with `machines.certifications` on,
    # members then need that type's certification to book it. Settable only while
    # `machines` is installed; null clears it.
    machine_type = serializers.IntegerField(allow_null=True, min_value=1, required=False)

    def to_internal_value(self, data):
        # Keep DRF's established read-only behavior for these server-owned
        # values. They never enter validated_data; their dedicated endpoints
        # retain the rules, activation and storage permissions.
        read_only = {"approval_mode", "image_key", "is_active"}
        unknown = set(data) - set(self.fields) - read_only if isinstance(data, dict) else set()
        if unknown:
            raise serializers.ValidationError({key: "Unexpected field." for key in sorted(unknown)})
        return super().to_internal_value(data)

    def validate(self, attrs):
        availability = attrs.get(
            'show_public_availability',
            getattr(self.instance, 'show_public_availability', False),
        )
        names = attrs.get(
            'show_public_booker_names',
            getattr(self.instance, 'show_public_booker_names', False),
        )
        if names and not availability:
            raise BookerNamesRequiresAvailability()
        return attrs


class BookableSpaceBookingRulesSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookableSpace
        fields = (
            'min_booking_duration_minutes',
            'max_booking_duration_minutes',
            'booking_lead_time_minutes',
            'max_booking_advance_days',
            'buffer_before_minutes',
            'buffer_after_minutes',
            'cancellation_cutoff_hours',
            'approval_mode',
        )


