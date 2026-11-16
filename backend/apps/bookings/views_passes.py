"""Private, throttled template/sample and single-booking pass endpoints."""
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from . import booking_authority
from .confirmation_access import owned_confirmation, private_response
from .models import Booking
from .pass_templates import normalize_pass_template
from .serializers_admin import EmptyActionSerializer
from .serializers_passes import BookingPassTemplateSerializer
from .services_passes import booking_pass, preview_pass, require_passes, save_pass_template
from .views_confirmation import ERRORS, PrivateBookingView

PDF_RESPONSES = {(200, "application/pdf"): OpenApiResponse(
    OpenApiTypes.BINARY, description="Private answer-free booking pass. Never contains a bearer QR."), **ERRORS}


class BookingPassRenderThrottle(UserRateThrottle):
    scope = "booking_pass_render"
    rate = "30/hour"


def pdf_response(payload):
    response = HttpResponse(payload, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="booking-pass.pdf"'
    return private_response(response)


class BookingPassTemplateView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [BookingPassRenderThrottle]

    @extend_schema(tags=["Admin bookings"], responses={200: BookingPassTemplateSerializer, **ERRORS},
                   description="Requires live resource edit_details and bookings.passes. Answer-free fields only.")
    def get(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        require_passes(space)
        return private_response(Response(normalize_pass_template(space.pass_template)))

    @extend_schema(tags=["Admin bookings"], request=BookingPassTemplateSerializer,
                   responses={200: BookingPassTemplateSerializer, **ERRORS})
    def put(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        require_passes(space)
        body = BookingPassTemplateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return private_response(Response(save_pass_template(space, body.validated_data, actor=request.user)))


class BookingPassPreviewView(BookingPassTemplateView):
    http_method_names = ["post", "options"]

    @extend_schema(tags=["Admin bookings"], request=BookingPassTemplateSerializer, responses=PDF_RESPONSES,
                   description="Requires edit_details. Fixed sample recipient only; no booking answers, notes, contacts or QR.")
    def post(self, request, pk):
        space = booking_authority.get_space(request.user, pk, "edit_details")
        require_passes(space)
        body = BookingPassTemplateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return pdf_response(preview_pass(space, body.validated_data, actor=request.user))


class BookingStaffPassView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [BookingPassRenderThrottle]

    @extend_schema(tags=["Admin bookings"], request=EmptyActionSerializer, responses=PDF_RESPONSES,
                   description="Requires resource check_in, bookings.passes/checkin and current active arrival. Answer-free projection, no override or cached PDF.")
    def post(self, request, pk, booking_id):
        space = booking_authority.get_space(request.user, pk, "check_in")
        require_passes(space)
        body = EmptyActionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        booking = get_object_or_404(Booking.objects.filter(space=space), pk=booking_id)
        return pdf_response(booking_pass(booking, actor=request.user, scanner=True))


class BookingMemberPassView(PrivateBookingView):
    throttle_classes = [BookingPassRenderThrottle]

    @extend_schema(tags=["Member bookings"], responses=PDF_RESPONSES,
                   description="Authenticated booking owner only. Confirmed/completed answer-free pass; bookings.passes required. No membership module needed.")
    def get(self, request, makerspace_slug, public_token):
        booking = owned_confirmation(request, makerspace_slug, public_token)
        return pdf_response(booking_pass(booking, actor=request.user))
