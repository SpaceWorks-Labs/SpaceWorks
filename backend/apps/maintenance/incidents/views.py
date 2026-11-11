"""Incident register routes: staff list/triage and the member's own reports (decision 223 (k)).

Every route answers 404 while `safety.incidents` is off. Staff reach is the area-narrowed
`scope.visible_incidents`; a member reads only reports they filed.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions_member import MemberPersonOnly
from apps.accounts.models import User
from apps.admin_api.permissions import IsActiveStaff
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.bookings.models import BookableSpace, Booking
from apps.events.models import Event
from apps.hardware_requests.models import HardwareRequest
from apps.machines.models import Machine
from apps.makerspaces.models import GuestPass, Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors

from . import scope, services
from .models import Incident, IncidentAction
from .serializers import (
    IncidentActionCreateSerializer, IncidentActionSerializer, IncidentActionUpdateSerializer, IncidentPageSerializer,
    IncidentSerializer, MemberIncidentPageSerializer, MemberIncidentReportSerializer, MemberIncidentSerializer,
    StaffIncidentCreateSerializer, StaffIncidentUpdateSerializer,
)

STAFF_TAGS, MEMBER_TAGS = ["Admin maintenance incidents"], ["Member incident reports"]
LINK_MODELS = {"guest_pass": GuestPass, "machine": Machine, "room": BookableSpace, "event": Event, "loan": HardwareRequest,
               "booking": Booking, "involved_user": User, "sponsor_user": User}


# Records are resolved inside the incident's space, so another space's id is a plain 404
# (never a 400 that confirms it exists elsewhere). People are checked by `_require_person`.
LINK_SPACE_FIELDS = {"booking": "space__makerspace", "involved_user": None, "sponsor_user": None}


def _fields(data, space):
    """Validated payload -> model fields: `<link>_id` becomes the row (a missing row is a 404)."""
    out = {}
    for key, value in data.items():
        name = key[:-3] if key.endswith("_id") else key
        if name in LINK_MODELS:
            field = LINK_SPACE_FIELDS.get(name, "makerspace")
            rows = LINK_MODELS[name].objects.filter(**{field: space}) if field else LINK_MODELS[name].objects.all()
            out[name] = None if value is None else get_object_or_404(rows, pk=value)
        elif name == "repair_issue":
            from apps.maintenance.models import IssueReport
            out[name] = None if value is None else get_object_or_404(IssueReport.objects.filter(makerspace=space), pk=value)
        else:
            out[key] = value
    return out


def _page(request, view, rows, serializer):
    paginator = PageNumberPagination()
    paginator.page_size = 24
    page = paginator.paginate_queryset(rows, request, view=view)
    return paginator.get_paginated_response(serializer(page, many=True).data)


def _staff_space(actor, makerspace_id):
    space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
    scope.require_incidents(space)
    if not scope.is_staff_reader(actor, space):
        raise PermissionDenied()
    return space


def _staff_incident(actor, pk, *, read_only=False):
    row = get_object_or_404(Incident.objects.select_related("makerspace", "reporter", "involved_user"), pk=pk)
    scope.require_incidents(row.makerspace)
    if not (scope.can_read(actor, row) if read_only else scope.can_triage(actor, row)):
        raise NotFound()
    return row


FILTERS = [OpenApiParameter("status", str, enum=[v for v, _ in Incident.Status.choices], required=False),
           OpenApiParameter("severity", str, enum=[v for v, _ in Incident.Severity.choices], required=False),
           OpenApiParameter("area", str, enum=[v for v, _ in Incident.Area.choices], required=False),
           OpenApiParameter("kind", str, enum=[v for v, _ in Incident.Kind.choices], required=False),
           OpenApiParameter("page", int, required=False),
           # Decision 242: subject filters (ids inside this space; an unknown id simply matches nothing).
           *[OpenApiParameter(name, int, required=False) for name in
             ("machine", "event", "booking", "room", "loan", "product", "person")]]
SUBJECT_FILTERS = {"machine": "machine_id", "event": "event_id", "booking": "booking_id", "room": "room_id",
                   "loan": "loan_id", "product": "loan__items__product_id", "person": "involved_user_id"}


class IncidentListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=STAFF_TAGS, summary="The incident register (area-narrowed)", request=None, parameters=FILTERS,
                   responses={200: IncidentPageSerializer, **errors(401, 403, 404)})
    def get(self, request, makerspace_id):
        space = _staff_space(request.user, makerspace_id)
        rows = scope.readable_incidents(request.user, space).select_related("reporter", "involved_user")
        for name in ("status", "severity", "area", "kind"):
            if request.query_params.get(name):
                rows = rows.filter(**{name: request.query_params[name]})
        for name, lookup in SUBJECT_FILTERS.items():
            if str(request.query_params.get(name, "")).isdigit():
                rows = rows.filter(**{lookup: int(request.query_params[name])})
        rows = rows.distinct()
        return _page(request, self, rows.prefetch_related("actions__assignee"), IncidentSerializer)

    @extend_schema(tags=STAFF_TAGS, summary="Record an incident as staff", request=StaffIncidentCreateSerializer,
                   responses={201: IncidentSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = _staff_space(request.user, makerspace_id)
        if not scope.can_record(request.user, space):  # decision 242(f): a Technician reads, never records
            raise PermissionDenied()
        serializer = StaffIncidentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = services.report(request.user, space, **_fields(serializer.validated_data, space))
        return Response(IncidentSerializer(incident).data, status=status.HTTP_201_CREATED)


class IncidentDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=STAFF_TAGS, summary="One incident with its follow-up actions", request=None,
                   responses={200: IncidentSerializer, **errors(401, 404)})
    def get(self, request, pk):
        return Response(IncidentSerializer(_staff_incident(request.user, pk, read_only=True)).data)

    @extend_schema(tags=STAFF_TAGS, summary="Triage: status, severity, links, resolution",
                   request=StaffIncidentUpdateSerializer,
                   responses={200: IncidentSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        row = _staff_incident(request.user, pk)
        serializer = StaffIncidentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(IncidentSerializer(services.update(request.user, row, **_fields(serializer.validated_data, row.makerspace))).data)


class IncidentActionListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=STAFF_TAGS, summary="Add a follow-up action", request=IncidentActionCreateSerializer,
                   responses={201: IncidentActionSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        row = _staff_incident(request.user, pk)
        serializer = IncidentActionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assignee = None
        if data.get("assignee_id"):
            # m27: the assignee must hold an active membership in this space; any other id answers the same
            # 400 as a missing one, so the id space cannot be probed for existence.
            from apps.makerspaces.models import MakerspaceMembership
            if not MakerspaceMembership.objects.filter(makerspace_id=row.makerspace_id, status="active",
                                                       user_id=data["assignee_id"]).exists():
                raise ValidationError({"assignee_id": "Choose a member of this space."})
            assignee = User.objects.get(pk=data["assignee_id"])
        action = services.add_action(request.user, row, description=data["description"], assignee=assignee,
                                     due_date=data.get("due_date"))
        return Response(IncidentActionSerializer(action).data, status=status.HTTP_201_CREATED)


class IncidentActionDetailView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=STAFF_TAGS, summary="Mark a follow-up action done or open", request=IncidentActionUpdateSerializer,
                   responses={200: IncidentActionSerializer, **errors(400, 401, 403, 404)})
    def patch(self, request, pk):
        action = get_object_or_404(IncidentAction.objects.select_related("incident__makerspace"), pk=pk)
        _staff_incident(request.user, action.incident_id)
        serializer = IncidentActionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(IncidentActionSerializer(
            services.set_action_done(request.user, action, done=serializer.validated_data["done"])).data)


class MemberIncidentView(APIView):
    permission_classes = [IsAuthenticated, MemberPersonOnly]
    throttle_classes = [MemberPrincipalRateThrottle]

    def _space(self, makerspace_id):
        space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        return scope.require_incidents(space)

    @extend_schema(tags=MEMBER_TAGS, summary="Incidents you reported", request=None,
                   parameters=[OpenApiParameter("page", int, required=False)],
                   responses={200: MemberIncidentPageSerializer, **errors(401, 404)})
    def get(self, request, makerspace_id):
        space = self._space(makerspace_id)
        return _page(request, self, Incident.objects.filter(makerspace=space, reporter=request.user),
                     MemberIncidentSerializer)

    @extend_schema(tags=MEMBER_TAGS, summary="Report an incident or near miss", request=MemberIncidentReportSerializer,
                   responses={201: MemberIncidentSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, makerspace_id):
        space = self._space(makerspace_id)
        serializer = MemberIncidentReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        incident = services.report(request.user, space, **_fields(serializer.validated_data, space))
        return Response(MemberIncidentSerializer(incident).data, status=status.HTTP_201_CREATED)
