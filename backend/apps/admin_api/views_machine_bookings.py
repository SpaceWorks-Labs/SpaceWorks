"""Decision 248 / MC11: a machine's time bookings, read-only, for the Machine Manager.

`machines.time_booking` books one machine's time through the bookings module, which a Machine Manager does not
manage (`manage_bookings`). This route lets them SEE who has the machine and when, narrowed to the machines their
role manages, and never decides or edits a booking -- the Booking Manager does that through the bookings routes.
"""

from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.guards import require_feature, require_module
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from django.utils.translation import gettext

FEATURE = "machines.time_booking"


class MachineBookingSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    machine_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    member_name = serializers.CharField(allow_blank=True)
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    status = serializers.CharField()


class _Pager(PageNumberPagination):
    page_size = 50


def _bound(request, key):
    raw = request.query_params.get(key)
    if not raw:
        return None
    value = parse_datetime(raw)
    if value is None:
        raise ValidationError({key: gettext("Use an ISO 8601 date and time.")})
    return value


class MachineBookingListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Admin machines"], summary="Machine-time bookings (read-only, narrowed to the machines you manage)",
        description="Requires manage_machines and `machines.time_booking`. Filters: `machine` (id), `from`, `to` "
                    "(ISO 8601). Newest first. Deciding a booking stays with manage_bookings.",
        parameters=[OpenApiParameter("machine", int), OpenApiParameter("from", str), OpenApiParameter("to", str),
                    OpenApiParameter("page", int)],
        responses={200: MachineBookingSerializer(many=True), 400: ErrorSerializer, 401: ErrorSerializer,
                   403: ErrorSerializer, 404: ErrorSerializer},
    )
    def get(self, request, makerspace_id):
        from apps.bookings.models import Booking
        from apps.machines.access_scoping import scope_machines_for_actor
        from apps.machines.models import Machine

        space = get_object_or_404(rbac.scope_by_action(
            request.user, rbac.Action.MANAGE_MACHINES, servable_queryset(), field="pk"), pk=makerspace_id)
        require_module(space, "machines")
        require_module(space, "bookings")
        require_feature(space, FEATURE)
        fleet = scope_machines_for_actor(request.user, Machine.objects.filter(makerspace=space))
        rows = Booking.objects.filter(space__makerspace=space, space__machine__in=fleet).select_related(
            "space__machine", "member").order_by("-starts_at", "-pk")
        if str(request.query_params.get("machine", "")).isdigit():
            rows = rows.filter(space__machine_id=int(request.query_params["machine"]))
        if (start := _bound(request, "from")) is not None:
            rows = rows.filter(ends_at__gte=start)
        if (end := _bound(request, "to")) is not None:
            rows = rows.filter(starts_at__lt=end)
        pager = _Pager()
        page = pager.paginate_queryset(rows, request, view=self)
        data = [{"id": b.pk, "machine_id": b.space.machine_id, "machine_name": b.space.machine.name,
                 "member_name": (b.member.display_name or b.member.username) if b.member_id else "",
                 "starts_at": b.starts_at, "ends_at": b.ends_at, "status": b.status} for b in page]
        return pager.get_paginated_response(MachineBookingSerializer(data, many=True).data)
