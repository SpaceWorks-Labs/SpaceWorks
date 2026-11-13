"""Read-only admission readiness for staff creating or reviewing a booking (decision 216 item 4).

No write and no audit. Authorization matches the staff create and quote views: the room's
`manage_reservations`, and a member drawn from the same eligible-member set.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff

from .admission_readiness import readiness
from .serializers_booking_readiness import BookingReadinessSerializer, StaffBookingReadinessQuerySerializer
from .views_admin_booking_actions import _manageable_booking
from .views_admin_booking_create import ERRORS, _members
from .views_admin_spaces import manageable_space

NO_STORE = {'Cache-Control': 'private, no-store'}


class StaffBookingReadinessView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'], summary='Preview what a staff booking would meet at admission',
        description='Requires `manage_reservations` on the room. Runs the room-outage, machine-repair and '
                    'certification admission checks without writing, and reports a maintenance lockout '
                    'as advisory. `member_id`, when sent, must be an eligible active member.',
        parameters=[StaffBookingReadinessQuerySerializer],
        responses={200: BookingReadinessSerializer, **ERRORS},
    )
    def get(self, request, pk):
        space = manageable_space(request.user, pk, "manage_reservations")
        query = StaffBookingReadinessQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        values = query.validated_data
        member = None
        if values.get('member_id'):
            member = get_object_or_404(_members(request.user, space), user_id=values['member_id']).user
        data = readiness(space, member=member, starts_at=values['starts_at'], ends_at=values['ends_at'],
                         actor=request.user)
        return Response(BookingReadinessSerializer(data).data, headers=NO_STORE)


class BookingReadinessView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=['Admin bookings'], summary="Readiness of an existing booking's room, machine and member",
        description='Requires `manage_reservations` on the booking\'s room. The same read-only checks as '
                    'the staff preview, for the booking\'s own window and member.',
        responses={200: BookingReadinessSerializer, **ERRORS},
    )
    def get(self, request, pk):
        booking = _manageable_booking(request.user, pk)
        data = readiness(booking.space, member=booking.member, starts_at=booking.starts_at,
                         ends_at=booking.ends_at, actor=request.user)
        return Response(BookingReadinessSerializer(data).data, headers=NO_STORE)
