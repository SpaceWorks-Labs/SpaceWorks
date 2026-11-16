"""Inputs and minimal identity choices for staff booking on behalf of a member."""

from collections.abc import Mapping

from django.utils.translation import gettext
from rest_framework import serializers

from apps.payments.pricing.serializers import PricingQuoteSerializer

from apps.bookings.serializers_public import PublicBookingInputSerializer


class StaffBookingInputSerializer(PublicBookingInputSerializer):
    member_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807)
    note = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    certification_override_reason = serializers.CharField(
        max_length=1000, allow_blank=True, required=False,
        help_text='Requires existing authority over the linked machine type; audited.',
    )

    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        unknown = set(data) - set(self.fields)
        if unknown:
            raise serializers.ValidationError({key: 'Unexpected field.' for key in sorted(unknown)})
        return super().to_internal_value(data)


_DIGEST = r'^[0-9a-f]{64}$'


class StaffSingleBookingInputSerializer(StaffBookingInputSerializer):
    """Single staff booking. Recurring creation keeps the unconfirmed base contract."""

    member_id = serializers.IntegerField(
        min_value=1, max_value=9223372036854775807, required=False,
        help_text='The active member booked for. Omit it only for a house booking.')
    house = serializers.BooleanField(
        required=False, default=False,
        help_text='Decision 223 (h): a staff-only house booking with no member booker. It is confirmed at '
                  'once, never charged and consumes no included plan hours. `member_id` must be omitted.')

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if bool(attrs.get('house')) == ('member_id' in attrs):
            raise serializers.ValidationError(
                {'member_id': gettext('Give a member_id, or set house to true without one.')})
        return attrs

    price_confirmation = serializers.RegexField(
        _DIGEST, required=False,
        help_text='Digest from the staff price preview; a moved price answers 409 price_changed '
                  'and creates neither a booking nor a charge.',
    )


class StaffBookingQuoteInputSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    replaces_booking_id = serializers.IntegerField(
        min_value=1, max_value=9223372036854775807, required=False,
        help_text='The rejected/cancelled booking being replaced; when it is event-linked the staff '
                  'replacement draws nothing from the plan included hours of the member (decision 221(d)).',
    )
    organization_id = serializers.IntegerField(
        min_value=1, max_value=9223372036854775807, required=False,
        help_text='Decision 223 (k): quote a partner-event booking for this organization; it draws nothing '
                  'from the member plan hours, so the preview must not count them (m8).',
    )

    def validate(self, attrs):
        if attrs['ends_at'] <= attrs['starts_at']:
            raise serializers.ValidationError({'ends_at': gettext('End time must be after start time.')})
        return attrs


class StaffBookingQuoteSerializer(serializers.Serializer):
    charges = serializers.ChoiceField(choices=['tracked', 'off'])
    quote = PricingQuoteSerializer(allow_null=True, help_text='Net room quote; null when charges are off.')
    included_hours = serializers.JSONField(
        allow_null=True,
        help_text='Decision 221(d): plan included hours this booking uses and the balance left '
                  '({kind, term_id, plan_name, term_ends_at, allowance_minutes, applied_minutes, '
                  'applied_hours, remaining_minutes, remaining_hours}); null when the term '
                  'includes none or the memberships module is off. Also shown with charges off.',
    )
    price_confirmation = serializers.RegexField(_DIGEST)


class BookingEligibleMemberSerializer(serializers.Serializer):
    member_id = serializers.IntegerField(source='user_id', read_only=True)
    display_name = serializers.SerializerMethodField()

    def get_display_name(self, obj) -> str:
        return obj.user.display_name or obj.user.get_full_name() or obj.user.username


class BookingEligibleMemberListSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True)
    previous = serializers.CharField(allow_null=True)
    results = BookingEligibleMemberSerializer(many=True)
