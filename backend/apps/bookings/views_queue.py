"""Cross-space Requests queue, booking Issues list/resolve, and staff/member departure records."""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.admin_api.serializers_payment_summary import scoped_payment_context
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace
from apps.payments.models import Payment

from . import booking_authority
from .models import Booking
from .models_departure import BookingIssue, DepartureSource
from .serializers_admin import BookingAdminSerializer, BookingListResponseSerializer
from .serializers_arrival import BookingArrivalSerializer
from .serializers_departure import (
    BookingIssueFilterSerializer, BookingIssuePageSerializer, BookingIssueSerializer,
    BookingQueueFilterSerializer, DepartureInputSerializer, IssueResolveSerializer,
)
from .serializers_member import MemberBookingSerializer
from .services_departure import record_departure, resolve_issue

ERRORS = {code: OpenApiResponse(ErrorSerializer, description=label) for code, label in (
    (400, "Invalid filter or body, or bookings disabled."), (401, "Sign in required."),
    (403, "No booking authority here."), (404, "Unknown or out-of-scope booking."),
    (409, "The booking is not in a state that allows this."), (423, "Tenant frozen."),
    (503, "Tenant write gate unavailable."),
)}


class _Page(PageNumberPagination):
    page_size = 24


def _reservation_spaces(actor, makerspace_id):
    makerspace = get_object_or_404(Makerspace.objects.all(), pk=makerspace_id)
    require_module(makerspace, "bookings")
    spaces = booking_authority.spaces_for(actor, "manage_reservations").filter(makerspace=makerspace)
    # A Booking Manager of a makerspace with no spaces yet gets an empty queue, not a 403;
    # only an actor with neither tenant booking authority nor a space grant here is refused.
    if not spaces.exists() and not rbac.can(actor, rbac.Action.MANAGE_BOOKINGS, makerspace.pk):
        raise PermissionDenied()
    return spaces


def _paged(view, request, queryset, serializer, extra=None, context=None):
    paginator = _Page()
    page = paginator.paginate_queryset(queryset, request, view=view)
    return Response({"count": paginator.page.paginator.count, **(extra or {}),
                     "next": paginator.get_next_link(), "previous": paginator.get_previous_link(),
                     "results": serializer(page, many=True, context=context(page) if context else {}).data})


class BookingQueueView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="Requests queue across every space this actor manages reservations for",
                   parameters=[BookingQueueFilterSerializer], responses={200: BookingListResponseSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        spaces = _reservation_spaces(request.user, makerspace_id)
        filters = BookingQueueFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data
        rows = Booking.objects.filter(space__in=spaces).select_related("space__makerspace")
        if data["status"] != "all":
            rows = rows.filter(status=data["status"])
        if data.get("space"):
            rows = rows.filter(space_id=data["space"])
        rows = rows.order_by(data["ordering"], "id")
        return _paged(self, request, rows, BookingAdminSerializer, context=lambda page: scoped_payment_context(
            request.user, rbac.Action.MANAGE_BOOKINGS, Payment.SubjectType.BOOKING, [row.pk for row in page]))


class BookingIssueListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="Issues raised at check-out (damaged, left early, something wrong)",
                   parameters=[BookingIssueFilterSerializer], responses={200: BookingIssuePageSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        spaces = _reservation_spaces(request.user, makerspace_id)
        filters = BookingIssueFilterSerializer(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data
        rows = BookingIssue.objects.filter(booking__space__in=spaces).select_related("booking__space", "departure")
        if data.get("space"):
            rows = rows.filter(booking__space_id=data["space"])
        open_count = rows.filter(resolved_at__isnull=True).count()
        if data["status"] != "all":
            rows = rows.filter(resolved_at__isnull=data["status"] == "open")
        return _paged(self, request, rows, BookingIssueSerializer, extra={"open_count": open_count})


class BookingIssueResolveView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="Resolve a booking issue", request=IssueResolveSerializer,
                   responses={200: BookingIssueSerializer, **ERRORS})
    def post(self, request, pk):
        visible = booking_authority.spaces_for(request.user, "manage_reservations")
        issue = get_object_or_404(BookingIssue.objects.filter(booking__space__in=visible), pk=pk)
        body = IssueResolveSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        resolved = resolve_issue(issue, actor=request.user, note=body.validated_data["note"])
        return Response(BookingIssueSerializer(resolved).data)


class BookingDepartView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"], summary="Record how a booking went when the booker leaves (staff)",
                   request=DepartureInputSerializer, responses={200: BookingArrivalSerializer, **ERRORS})
    def post(self, request, pk, booking_id):
        from .arrival_projection import arrival_data
        from .confirmation_access import private_response
        space = booking_authority.get_space(request.user, pk, "view")
        candidate = get_object_or_404(Booking.objects.filter(space=space), pk=booking_id)
        body = DepartureInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        booking = record_departure(candidate, actor=request.user, source=DepartureSource.STAFF, **body.validated_data)
        return private_response(Response(BookingArrivalSerializer(arrival_data(booking)).data))


class MemberBookingCheckoutView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]
    throttle_scope = "booking_submit"

    @extend_schema(tags=["Member bookings"], summary="Check out of my booking with a leave remark",
                   request=DepartureInputSerializer, responses={200: MemberBookingSerializer, **ERRORS})
    def post(self, request, makerspace_slug, public_token):
        from .views_member import own_bookings
        booking = get_object_or_404(own_bookings(request, makerspace_slug), public_token=public_token)
        body = DepartureInputSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        booking = record_departure(booking, actor=request.user, source=DepartureSource.MEMBER, **body.validated_data)
        return Response(MemberBookingSerializer(booking).data)
