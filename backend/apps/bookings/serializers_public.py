from django.utils.translation import gettext
from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.bookings import storage
from apps.bookings.busy_overlay import PublicBusyBlockSerializer
from apps.bookings.models import BookableSpace, Booking


PUBLIC_BOOKABLE_SPACE_FIELDS = (
    'public_token',
    'name',
    'kind',
    'description',
    'capacity',
    'location',
    'image_url',
    'photos',
    'approval_mode',
    'custom_form',
    'show_public_availability',
    'show_public_booker_names',
)


class PublicSpacePhotoSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    url = serializers.CharField(read_only=True)
    caption = serializers.CharField(read_only=True, allow_blank=True)


class PublicBookableSpaceSerializer(serializers.Serializer):
    public_token = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    kind = serializers.ChoiceField(
        choices=BookableSpace.Kind.choices,
        read_only=True,
    )
    description = serializers.CharField(read_only=True)
    capacity = serializers.IntegerField(min_value=0, read_only=True)
    location = serializers.CharField(read_only=True)
    image_url = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    approval_mode = serializers.ChoiceField(
        choices=BookableSpace.ApprovalMode.choices,
        read_only=True,
    )
    custom_form = serializers.JSONField(allow_null=True, read_only=True)
    show_public_availability = serializers.BooleanField(read_only=True)
    show_public_booker_names = serializers.BooleanField(read_only=True)

    @extend_schema_field(serializers.CharField(allow_blank=True))
    def get_image_url(self, obj):
        return storage.public_url(obj.image_key)

    @extend_schema_field(PublicSpacePhotoSerializer(many=True))
    def get_photos(self, obj):
        from .services_gallery import public_photos
        return public_photos(obj)


class PublicSpaceAvailabilityQuerySerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        errors = {}
        for field in ('starts_at', 'ends_at'):
            raw = self.initial_data.get(field)
            parsed = parse_datetime(raw) if isinstance(raw, str) else raw
            if parsed is None or timezone.is_naive(parsed):
                errors[field] = 'Datetime must include a timezone offset.'
        if errors:
            raise serializers.ValidationError(errors)

        starts_at = attrs['starts_at']
        ends_at = attrs['ends_at']
        if ends_at <= starts_at:
            raise serializers.ValidationError(
                {'ends_at': gettext('End time must be after start time.')}
            )
        if ends_at <= timezone.now():
            raise serializers.ValidationError(
                {'ends_at': gettext('End time must be in the future.')}
            )
        if ends_at - starts_at > timedelta(days=31):
            raise serializers.ValidationError(
                {'ends_at': gettext('Availability window cannot exceed 31 days.')}
            )
        return attrs


class PublicAvailabilityIntervalSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)
    booker_name = serializers.CharField(allow_null=True, read_only=True)
    tentative = serializers.BooleanField(read_only=True, default=False, help_text='A pending event hold; never names its booker.')


class PublicOpeningIntervalSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)


class PublicSpaceAvailabilitySerializer(serializers.Serializer):
    public_token = serializers.UUIDField(read_only=True)
    starts_at = serializers.DateTimeField(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)
    timezone = serializers.CharField(read_only=True)
    opening_intervals = PublicOpeningIntervalSerializer(
        many=True, read_only=True,
        help_text='Open windows in UTC, accounting for makerspace hours and dated exceptions.',
    )
    availability = PublicAvailabilityIntervalSerializer(
        many=True,
        allow_null=True,
        read_only=True,
    )
    unavailable = PublicBusyBlockSerializer(
        many=True, read_only=True,
        help_text='Time the room cannot be booked: `closed` outside opening hours, `unavailable` '
                  'otherwise (room out of service or its machine under repair, never detailed). '
                  '`unavailable` is listed only when the room shows public availability.',
    )


class PublicBookingInputSerializer(serializers.Serializer):
    certification_override_reason = serializers.CharField(required=False, allow_blank=True, max_length=1000, write_only=True)
    starts_at = serializers.DateTimeField(write_only=True)
    ends_at = serializers.DateTimeField(write_only=True)
    custom_answers = serializers.JSONField(
        allow_null=True,
        required=False,
        write_only=True,
    )
    event_id = serializers.IntegerField(
        min_value=1, required=False, allow_null=True, write_only=True,
        help_text="Optional, machine-time bookings only: an event I may act for in this makerspace (decision 342).")

    def validate(self, attrs):
        errors = {}
        for field in ('starts_at', 'ends_at'):
            raw = self.initial_data.get(field)
            parsed = parse_datetime(raw) if isinstance(raw, str) else raw
            if parsed is None or timezone.is_naive(parsed):
                errors[field] = 'Datetime must include a timezone offset.'
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class PublicBookingResponseSerializer(serializers.Serializer):
    public_token = serializers.UUIDField(read_only=True, required=False)
    confirmation_available = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_confirmation_available(self, booking):
        from apps.makerspaces.platform import feature_enabled
        return feature_enabled(booking.space.makerspace, "bookings.confirmations")

    status = serializers.ChoiceField(
        choices=(Booking.Status.PENDING, Booking.Status.CONFIRMED),
        read_only=True,
    )
    amount_due = serializers.SerializerMethodField()
    currency = serializers.SerializerMethodField()
    pay_online = serializers.SerializerMethodField()

    def _money(self, booking):
        from apps.bookings.response_money import booking_money
        return booking_money(booking)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_amount_due(self, booking):
        return self._money(booking)["amount_due"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_currency(self, booking):
        return self._money(booking)["currency"]

    @extend_schema_field(serializers.BooleanField())
    def get_pay_online(self, booking):
        return self._money(booking)["pay_online"]
