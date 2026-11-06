"""Staff image actions, pagination envelopes and reservation filters."""

from django.utils.translation import gettext
from rest_framework import serializers

from apps.bookings.models import Booking

from .serializers_reservation import BookingAdminSerializer
from .serializers_space_admin import BookableSpaceAdminSerializer


class SpaceImagePresignRequestSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=100)


class SpaceImageUploadSerializer(serializers.Serializer):
    url = serializers.URLField()
    method = serializers.ChoiceField(choices=('PUT',), required=False)
    fields = serializers.DictField(required=False)
    headers = serializers.DictField(required=False)


class SpaceImagePresignResponseSerializer(serializers.Serializer):
    object_key = serializers.CharField()
    upload = SpaceImageUploadSerializer()


class SpaceImageFinalizeRequestSerializer(serializers.Serializer):
    object_key = serializers.CharField(max_length=500)


class EmptyActionSerializer(serializers.Serializer):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if data:
            raise serializers.ValidationError(
                {field: 'Unexpected field.' for field in data}
            )
        return value


class BookableSpaceListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = BookableSpaceAdminSerializer(many=True)


class BookingListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.CharField(allow_null=True, required=False)
    previous = serializers.CharField(allow_null=True, required=False)
    results = BookingAdminSerializer(many=True)


class BookingListFilterSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1, max_value=9223372036854775807, required=False)
    status = serializers.ChoiceField(choices=Booking.Status.choices, required=False)
    starts_at = serializers.DateTimeField(required=False)
    ends_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if (
            attrs.get('starts_at')
            and attrs.get('ends_at')
            and attrs['ends_at'] < attrs['starts_at']
        ):
            raise serializers.ValidationError(
                {'ends_at': gettext('End of window must be at or after its start.')}
            )
        return attrs
