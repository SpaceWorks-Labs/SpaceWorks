"""Staff free/busy for one room around a requested window (decision 216, event hall picker)."""

from datetime import timedelta

from django.utils.translation import gettext
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from .busy_overlay import StaffBusyBlockSerializer
from .event_labels import LinkedEventLabelSerializer
from .staff_availability import availability
from .views_admin_booking_create import ERRORS
from .views_admin_spaces import manageable_space

NO_STORE = {'Cache-Control': 'private, no-store'}
MAX_WINDOW = timedelta(days=14)


class StaffAvailabilityQuerySerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

    def validate(self, attrs):
        if attrs['ends_at'] <= attrs['starts_at']:
            raise serializers.ValidationError({'ends_at': gettext('End time must be after start time.')})
        if attrs['ends_at'] - attrs['starts_at'] > MAX_WINDOW:
            raise serializers.ValidationError({'ends_at': gettext('Check at most 14 days at a time.')})
        return attrs


class BusyLabelSerializer(LinkedEventLabelSerializer):
    kind = serializers.ChoiceField(
        choices=['booking', 'event', 'reserved'],
        help_text='`booking` is an ordinary booking; `event` names an event this viewer may see; '
                  '`reserved` holds the room for an event the viewer may not see.')


class OpenIntervalSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class BusyWindowSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    starts_at = serializers.DateTimeField(help_text='Occupied start, including the room\'s before-buffer.')
    ends_at = serializers.DateTimeField(help_text='Occupied end, including the room\'s after-buffer.')
    booking_starts_at = serializers.DateTimeField()
    booking_ends_at = serializers.DateTimeField()
    label = BusyLabelSerializer()
    tentative = serializers.BooleanField(
        required=False, help_text='Decision 223 (m): a pending booking that holds a room for an event; '
        'it holds its slot until approved or rejected.')


class PendingWindowSerializer(serializers.Serializer):
    booking_id = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    label = BusyLabelSerializer()


class RequestedWindowSerializer(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    within_rules = serializers.BooleanField(help_text='Duration, lead time, advance limit and opening hours allow it.')
    rule_detail = serializers.CharField(allow_blank=True)
    conflict = serializers.BooleanField(help_text='Overlaps a confirmed booking (buffers included).')
    holds_room_on_create = serializers.BooleanField(
        help_text='Instant rooms confirm on create, so a conflict refuses the booking; approval rooms '
                  'create a pending booking that holds nothing and is refused at approval instead.')


class StaffAvailabilitySerializer(serializers.Serializer):
    space_id = serializers.IntegerField()
    timezone = serializers.CharField()
    range_starts_at = serializers.DateTimeField()
    range_ends_at = serializers.DateTimeField()
    opening_intervals = OpenIntervalSerializer(many=True)
    busy = BusyWindowSerializer(many=True, help_text='Confirmed bookings: the only bookings that hold the room.')
    pending = PendingWindowSerializer(many=True, help_text='Awaiting approval; they do not hold the room.')
    requested = RequestedWindowSerializer()
    unavailable = StaffBusyBlockSerializer(many=True, help_text=(
        'Room outage (block or warn), machine repair and closed time over the range (`busy_overlay`).'))


class StaffBookingAvailabilityView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'], summary="Free/busy for a room around a staff booking's window",
        description='Requires `manage_reservations` on the room. Read-only, no audit. Covers the whole '
                    'local day(s) the window touches: opening hours, confirmed busy time (buffers '
                    'included) and pending bookings, each labelled with its linked event only for a '
                    'viewer who may see that event. `requested` previews what admission will decide; '
                    'submit re-verifies everything. `unavailable` shows room outages, machine repair and closed '
                    'time; the readiness preview still runs those admission seams.',
        parameters=[StaffAvailabilityQuerySerializer],
        responses={200: StaffAvailabilitySerializer, **ERRORS},
    )
    def get(self, request, pk):
        space = manageable_space(request.user, pk, "manage_reservations")
        query = StaffAvailabilityQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = availability(request.user, space, **query.validated_data)
        return Response(StaffAvailabilitySerializer(data).data, headers=NO_STORE)
