"""Authenticated owner-only booking confirmation, PNG and one-booking calendar."""
from uuid import uuid4
from django.db import transaction
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from apps.hardware_requests.exceptions import ErrorSerializer
from .confirmation_access import owned_confirmation, private_response, require_feature
from .confirmation_render import confirmation_data, confirmation_png, qr_available
from .serializers_arrival import BookingConfirmationSerializer
from .serializers_admin import EmptyActionSerializer

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 429, 423, 503)}


class BookingConfirmationThrottle(UserRateThrottle):
    scope = "booking_confirmation"
    rate = "60/hour"


class PrivateBookingView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [BookingConfirmationThrottle]


class BookingConfirmationView(PrivateBookingView):
    @extend_schema(tags=["Member bookings"], responses={200: BookingConfirmationSerializer, **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        booking = owned_confirmation(request, makerspace_slug, public_token)
        return private_response(Response(BookingConfirmationSerializer(confirmation_data(booking)).data))


class BookingConfirmationPngView(PrivateBookingView):
    @extend_schema(tags=["Member bookings"], responses={
        (200, "image/png"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        from .services_bookings import _audit
        booking = owned_confirmation(request, makerspace_slug, public_token)
        if not qr_available(booking):
            raise NotFound()
        png = confirmation_png(booking)
        _audit(booking.space, request.user, "booking.confirmation_downloaded", booking)
        response = HttpResponse(png, content_type="image/png")
        response["Content-Disposition"] = 'attachment; filename="booking-confirmation.png"'
        return private_response(response)


class BookingConfirmationCalendarView(PrivateBookingView):
    @extend_schema(tags=["Member bookings"], responses={
        (200, "text/calendar"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS})
    def get(self, request, makerspace_slug, public_token):
        from .calendar_render import booking_calendar
        from .services_bookings import _audit
        booking = owned_confirmation(request, makerspace_slug, public_token)
        _audit(booking.space, request.user, "booking.calendar_downloaded", booking)
        response = HttpResponse(booking_calendar([booking]), content_type="text/calendar; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="booking.ics"'
        return private_response(response)


class BookingCredentialRotateView(PrivateBookingView):
    @extend_schema(tags=["Member bookings"], request=EmptyActionSerializer,
                   responses={200: BookingConfirmationSerializer, **ERRORS})
    def post(self, request, makerspace_slug, public_token):
        from .services_bookings import _audit, _locked_booking
        body = EmptyActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        candidate = owned_confirmation(request, makerspace_slug, public_token)
        with transaction.atomic():
            space, booking = _locked_booking(candidate)
            # Recheck ownership/account/module after waiting for the domain locks.
            owned_confirmation(request, makerspace_slug, public_token)
            booking.space = space
            require_feature(space.makerspace, "bookings.checkin")
            if not qr_available(booking):
                raise NotFound()
            booking.checkin_token = uuid4()
            booking.save(update_fields=["checkin_token"])
            _audit(space, request.user, "booking.checkin_credential_rotated", booking)
        return private_response(Response(BookingConfirmationSerializer(confirmation_data(booking)).data))
