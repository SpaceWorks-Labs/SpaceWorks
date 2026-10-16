"""Resource-scoped staff mutations; all policy is rechecked inside the services."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_payment_summary import scoped_payment_context
from apps.hardware_requests.view_helpers import ERROR_400, ERROR_401, ERROR_403, ERROR_404, ERROR_409, ERROR_429, ERROR_503
from apps.payments.models import Payment

from . import booking_authority
from .serializers_admin import BookingAdminSerializer, BookableSpaceAdminSerializer, EmptyActionSerializer
from .serializers_staff_tools import (
    BookingCloneInputSerializer, BookingDetailsInputSerializer, BookingTimeInputSerializer,
)
from .services_clone import clone_space
from .services_restore import restore_booking
from .services_staff_edit import edit_booking_details, edit_booking_time
from .views_admin_booking_actions import _manageable_booking

ERRORS = {400: ERROR_400, 401: ERROR_401, 403: ERROR_403, 404: ERROR_404, 409: ERROR_409, 429: ERROR_429}


class BookingToolsThrottle(UserRateThrottle):
    scope = "booking_staff_tools"
    rate = "60/hour"


class BookingCloneView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [BookingToolsThrottle]

    @extend_schema(tags=["Admin bookings"], summary="Clone a resource into a private copy",
                   description="Requires tenant MANAGE_BOOKINGS and bookings.clone. Copying protected rules also requires MANAGE_MAKERSPACE.",
                   request=BookingCloneInputSerializer, responses={201: BookableSpaceAdminSerializer, **ERRORS, 503: ERROR_503})
    def post(self, request, pk):
        space = booking_authority.get_space(request.user, pk, None)
        serializer = BookingCloneInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.evidence.storage import StorageUnavailable
        from apps.evidence.responses import storage_unavailable_response
        try:
            clone = clone_space(space, actor=request.user, **serializer.validated_data)
        except StorageUnavailable:
            return storage_unavailable_response()
        return Response(BookableSpaceAdminSerializer(clone, context={"actor": request.user}).data, status=201)


class _BookingToolsView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [BookingToolsThrottle]

    def execute(self, request, pk, serializer_class, operation):
        booking = _manageable_booking(request.user, pk)
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = operation(booking, actor=request.user, **serializer.validated_data)
        context = scoped_payment_context(request.user, rbac.Action.MANAGE_BOOKINGS,
                                         Payment.SubjectType.BOOKING, [booking.pk])
        return Response(BookingAdminSerializer(booking, context=context).data)


class BookingDetailsEditView(_BookingToolsView):
    @extend_schema(tags=["Admin bookings"], summary="Edit private reservation note or answers",
                   description="Requires resource manage_reservations and bookings.staff_tools. Unknown fields are refused; answers use the current schema.",
                   request=BookingDetailsInputSerializer, responses={200: BookingAdminSerializer, **ERRORS})
    def patch(self, request, pk):
        return self.execute(request, pk, BookingDetailsInputSerializer, edit_booking_details)


class BookingTimeEditView(_BookingToolsView):
    @extend_schema(tags=["Admin bookings"], summary="Move a pending or confirmed reservation",
                   description="Requires resource manage_reservations and bookings.staff_tools. Both old and proposed windows must be beyond the cutoff; ordinary admission rules apply. Identity, status and flat charge are preserved.",
                   request=BookingTimeInputSerializer, responses={200: BookingAdminSerializer, **ERRORS})
    def post(self, request, pk):
        return self.execute(request, pk, BookingTimeInputSerializer, edit_booking_time)


class BookingRestoreView(_BookingToolsView):
    @extend_schema(tags=["Admin bookings"], summary="Undo a recent cancellation without money movement",
                   description="Requires resource manage_reservations and bookings.staff_tools. Within five minutes, restore the exact pending/confirmed state under current admission. Any historical or newly required charge refuses undo.",
                   request=EmptyActionSerializer, responses={200: BookingAdminSerializer, **ERRORS})
    def post(self, request, pk):
        return self.execute(request, pk, EmptyActionSerializer, restore_booking)
