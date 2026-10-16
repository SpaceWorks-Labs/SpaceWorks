"""Member booking projections contain only the caller's own reservations."""

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.bookings.models import Booking
from apps.bookings.services_schedule import cancellation_cutoff, member_can_cancel


class MemberBookingSerializer(serializers.ModelSerializer):
    space_name = serializers.CharField(source='space.name', read_only=True)
    timezone = serializers.CharField(source='space.makerspace.timezone', read_only=True)
    cancellation_cutoff_at = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    confirmation_available = serializers.SerializerMethodField()
    decision_reason = serializers.CharField(read_only=True)
    departed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    can_checkout = serializers.SerializerMethodField()
    departure_outcome = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_can_checkout(self, booking):
        from apps.bookings.services_departure import can_depart
        return can_depart(booking, now=self.context.get('now') or timezone.now(), source="member")

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_departure_outcome(self, booking):
        return booking.departure_events.values_list("outcome", flat=True).first()

    @extend_schema_field(serializers.BooleanField())
    def get_confirmation_available(self, booking):
        from apps.makerspaces.platform import feature_enabled
        return feature_enabled(booking.space.makerspace, "bookings.confirmations")

    class Meta:
        model = Booking
        fields = ('public_token', 'space_name', 'timezone', 'starts_at', 'ends_at',
                  'status', 'cancellation_cutoff_at', 'can_cancel', 'confirmation_available',
                  'decision_reason', 'departed_at', 'can_checkout', 'departure_outcome')
        read_only_fields = fields

    @extend_schema_field(serializers.DateTimeField())
    def get_cancellation_cutoff_at(self, booking):
        return cancellation_cutoff(booking)

    @extend_schema_field(serializers.BooleanField())
    def get_can_cancel(self, booking):
        return booking.arrived_at is None and member_can_cancel(booking, now=self.context.get('now') or timezone.now())


class MemberBookingListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = MemberBookingSerializer(many=True)


class MemberBookingFilterSerializer(serializers.Serializer):
    period = serializers.ChoiceField(choices=('upcoming', 'past'), default='upcoming')
