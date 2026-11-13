"""Resource-only campaign API; no tenant directory or recipient contacts."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import UserRateThrottle

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from . import booking_authority
from .booking_permissions import MANAGE_RESERVATIONS
from .broadcasts import authorize
from .models_broadcasts import BookingBroadcast
from .serializers_broadcasts import (
    BookingBroadcastActionSerializer, BookingBroadcastInputSerializer,
    BookingBroadcastListSerializer, BookingBroadcastSerializer,
)
from .services_broadcasts import change, compose
from .views_grant_pagination import PAGE_PARAMETERS, paginated

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 423, 429, 503)}
DESCRIPTION = ("Requires live resource manage_reservations authority, bookings.broadcasts, notifications and email. "
               "Verified account email only; membership consent, preferences, requester toggle, matrix and quiet hours apply.")


def private_response(campaign, status=200):
    response = Response(BookingBroadcastSerializer(campaign).data, status=status)
    response["Cache-Control"] = "private, no-store"
    return response


class BookingBroadcastThrottle(UserRateThrottle):
    scope = "booking_broadcast"
    rate = "120/min"


class BookingBroadcastListView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [BookingBroadcastThrottle]

    def space(self, actor, pk):
        space = booking_authority.get_space(actor, pk, MANAGE_RESERVATIONS)
        authorize(BookingBroadcast(space=space, makerspace=space.makerspace), actor)
        return space

    @extend_schema(tags=["Admin bookings"], description=DESCRIPTION, parameters=PAGE_PARAMETERS,
                   responses={200: BookingBroadcastListSerializer, **ERRORS})
    def get(self, request, pk):
        space = self.space(request.user, pk)
        return paginated(request, space.broadcasts.filter(makerspace=space.makerspace).order_by("-created_at", "-pk"),
                         BookingBroadcastSerializer)

    @extend_schema(tags=["Admin bookings"], description=DESCRIPTION + " Compose a draft for a future start window of at most 366 days.",
                   request=BookingBroadcastInputSerializer, responses={201: BookingBroadcastSerializer, **ERRORS})
    def post(self, request, pk):
        space = self.space(request.user, pk)
        payload = BookingBroadcastInputSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return private_response(compose(space, request.user, **payload.validated_data), 201)


class BookingBroadcastActionView(APIView):
    permission_classes = [IsActiveStaff]
    throttle_classes = [BookingBroadcastThrottle]
    action = "queue"

    @extend_schema(tags=["Admin bookings"], description=DESCRIPTION + " Queue limit: ten per hour per tenant; cancel stops unclaimed sends.",
                   request=None, responses={200: BookingBroadcastSerializer, **ERRORS})
    def post(self, request, pk, campaign_id):
        space = booking_authority.get_space(request.user, pk, MANAGE_RESERVATIONS)
        campaign = get_object_or_404(BookingBroadcast, space=space, makerspace=space.makerspace, pk=campaign_id)
        payload = BookingBroadcastActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        return private_response(change(campaign, request.user, self.action))
