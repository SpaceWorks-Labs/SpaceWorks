"""Minimal scanner API; credentials only enter POST bodies, never URL paths."""
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from apps.admin_api.permissions import IsActiveStaff
from . import booking_authority
from .arrival_projection import arrival_data
from .confirmation_access import private_response
from .models import Booking
from .serializers_arrival import BookingArrivalSerializer, BookingCredentialSerializer
from .serializers_admin import EmptyActionSerializer
from .services_arrival import confirm_arrival, resolve_booking, reverse_arrival, require_arrival_access
from .views_confirmation import PrivateBookingView, ERRORS


class BookingScannerThrottle(UserRateThrottle):
    scope = "booking_scanner"
    rate = "120/minute"


@method_decorator(sensitive_post_parameters("credential"), name="dispatch")
class BookingScannerView(PrivateBookingView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [BookingScannerThrottle]

    def credential(self, request):
        serializer = BookingCredentialSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data["credential"]


class BookingArrivalResolveView(BookingScannerView):
    @extend_schema(tags=["Admin bookings"], request=BookingCredentialSerializer,
                   responses={200: BookingArrivalSerializer, **ERRORS})
    @sensitive_variables()
    def post(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "check_in")
        booking = resolve_booking(space, self.credential(request), actor=request.user)
        return private_response(Response(BookingArrivalSerializer(arrival_data(booking)).data))


class BookingArrivalConfirmView(BookingScannerView):
    @extend_schema(tags=["Admin bookings"], request=BookingCredentialSerializer,
                   responses={200: BookingArrivalSerializer, **ERRORS})
    @sensitive_variables()
    def post(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "check_in")
        booking = confirm_arrival(space, self.credential(request), actor=request.user)
        return private_response(Response(BookingArrivalSerializer(arrival_data(booking)).data))


class BookingArrivalReverseView(BookingScannerView):
    @extend_schema(tags=["Admin bookings"], request=EmptyActionSerializer,
                   responses={200: BookingArrivalSerializer, **ERRORS})
    def post(self, request, pk, booking_id):
        space = booking_authority.get_space(request.user, pk, "check_in")
        require_arrival_access(request.user, space)
        body = EmptyActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        candidate = get_object_or_404(Booking.objects.filter(space=space), pk=booking_id)
        booking = reverse_arrival(candidate, actor=request.user)
        return private_response(Response(BookingArrivalSerializer(arrival_data(booking)).data))
