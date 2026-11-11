"""Supervised workshop sessions (decision 223 (d)): the instructor's surface.

The instructor may be a member, so these live on the member prefix. Authority is the
service's: only a certified instructor opens, and only that instructor (or a manager of the
machine) adds supervisees, records uses or closes. Every route answers 404 while
`machines.supervised_sessions` is off.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions_member import MemberPersonOnly
from apps.accounts.models import User
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.events.models import Event, EventRegistration
from apps.makerspaces.guards import module_off
from apps.makerspaces.models import Makerspace
from apps.makerspaces.platform import module_enabled
from apps.makerspaces.servability import servable_queryset
from apps.openapi_errors import errors
from apps.presence.models import PresenceSession

from . import access, supervised
from .models import Machine, SupervisedSession, SupervisedUse
from .serializers_workshop import (
    SupervisedActionSerializer, SupervisedSessionOpenSerializer, SupervisedSessionPageSerializer,
    SupervisedSessionSerializer, SupervisedSuperviseeSerializer, SupervisedUseSerializer, SupervisedUseStartSerializer,
)

TAGS = ["Member supervised sessions"]
CODES = errors(400, 401, 403, 404, 409)


class _Base(APIView):
    permission_classes = [IsAuthenticated, MemberPersonOnly]
    throttle_classes = [MemberPrincipalRateThrottle]


def _session(request, pk):
    row = get_object_or_404(SupervisedSession.objects.select_related(
        "makerspace", "machine__machine_type", "instructor"), pk=pk)
    supervised.require_supervised(row.makerspace)
    if row.instructor_id != request.user.pk and not access.can_manage_machine(request.user, row.machine):
        raise NotFound()
    return row


def _detail(row):
    row = SupervisedSession.objects.prefetch_related("participants__user", "uses").select_related(
        "machine", "instructor").get(pk=row.pk)
    return SupervisedSessionSerializer(row).data


def supervisee_pool(session):
    """People who may join: checked in at the space now, or registered for the linked event."""
    pool = Q(pk__in=PresenceSession.objects.filter(
        makerspace=session.makerspace, ended_at__isnull=True, expires_at__gt=timezone.now()).values("account_id"))
    if session.event_id and module_enabled(session.makerspace, "events"):  # decision 218: Events off, no registrants
        pool |= Q(pk__in=EventRegistration.objects.filter(
            event_id=session.event_id, member__isnull=False,
            status__in=[EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED],
        ).values("member_id"))
    return pool


def _user(session, user_id, *, joining=False):
    # Final audit 0.12.0: only this session's own people (and, to join, the picker's pool), never
    # any platform id -- the response names every participant, so a bare id leaked other tenants.
    allowed = Q(pk__in=session.participants.values("user_id"))
    if joining:
        allowed |= supervisee_pool(session)
    return get_object_or_404(User.objects.filter(allowed, is_active=True), pk=user_id)


class SupervisedSessionOpenView(_Base):
    @extend_schema(tags=TAGS, summary="Open a supervised session on a machine", request=SupervisedSessionOpenSerializer,
                   responses={201: SupervisedSessionSerializer, **CODES})
    def post(self, request, machine_id):
        machine = get_object_or_404(servable_queryset(Machine.objects.select_related("makerspace", "machine_type").filter(
            pk=machine_id, is_active=True), relation="makerspace"))
        supervised.require_supervised(machine.makerspace)
        serializer = SupervisedSessionOpenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event_id = serializer.validated_data.get("event_id")
        if event_id and not module_enabled(machine.makerspace, "events"):
            raise module_off("events")  # decision 218: no event binding while Events is off
        event = get_object_or_404(Event.objects.filter(makerspace=machine.makerspace), pk=event_id) if event_id else None
        row = supervised.open_session(machine, request.user, event=event, note=serializer.validated_data["note"])
        return Response(_detail(row), status=status.HTTP_201_CREATED)


class SupervisedSessionListView(_Base):
    @extend_schema(tags=TAGS, summary="Supervised sessions you lead (all, for a machine manager)", request=None,
                   parameters=[OpenApiParameter("status", str, enum=["open", "closed"], required=False),
                               OpenApiParameter("machine", int, required=False, description="Only sessions on this machine id."),
                               OpenApiParameter("page", int, required=False)],
                   responses={200: SupervisedSessionPageSerializer, **errors(401, 404)})
    def get(self, request, makerspace_id):
        space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        supervised.require_supervised(space)
        rows = SupervisedSession.objects.filter(makerspace=space).select_related("machine", "instructor")
        rows = rows.prefetch_related("participants__user", "uses")
        led = rows.filter(instructor=request.user)
        managed = [row.pk for row in rows.exclude(instructor=request.user)
                   if access.can_manage_machine(request.user, row.machine)]
        rows = rows.filter(pk__in=[*led.values_list("pk", flat=True), *managed])
        wanted = request.query_params.get("status")
        if wanted in {"open", "closed"}:
            rows = rows.filter(closed_at__isnull=wanted == "open")
        machine = request.query_params.get("machine")
        if machine:
            if not machine.isdecimal() or not 0 < int(machine) <= 9223372036854775807:
                raise ValidationError({"machine": gettext("Choose a valid machine.")})
            rows = rows.filter(machine_id=int(machine))
        paginator = PageNumberPagination()
        paginator.page_size = 24
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(SupervisedSessionSerializer(page, many=True).data)


class SupervisedSessionDetailView(_Base):
    @extend_schema(tags=TAGS, summary="One supervised session with its supervisees and uses", request=None,
                   responses={200: SupervisedSessionSerializer, **errors(401, 404)})
    def get(self, request, pk):
        return Response(_detail(_session(request, pk)))


class SupervisedSuperviseeView(_Base):
    @extend_schema(tags=TAGS, summary="Add a supervisee", request=SupervisedSuperviseeSerializer,
                   responses={200: SupervisedSessionSerializer, **CODES})
    def post(self, request, pk):
        session = _session(request, pk)
        serializer = SupervisedSuperviseeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        supervised.add_supervisee(session, _user(session, serializer.validated_data["user_id"], joining=True),
                                  actor=request.user)
        return Response(_detail(session))


class SupervisedSuperviseeRemoveView(_Base):
    @extend_schema(tags=TAGS, summary="Remove a supervisee (ends their open use)", request=None,
                   responses={200: SupervisedSessionSerializer, **CODES})
    def delete(self, request, pk, user_id):
        session = _session(request, pk)
        supervised.remove_supervisee(session, _user(session, user_id), actor=request.user)
        return Response(_detail(session))


class SupervisedUseStartView(_Base):
    @extend_schema(tags=TAGS, summary="Record a supervisee starting a use of the machine",
                   request=SupervisedUseStartSerializer, responses={201: SupervisedUseSerializer, **CODES})
    def post(self, request, pk):
        session = _session(request, pk)
        serializer = SupervisedUseStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        use = supervised.start_use(session, _user(session, serializer.validated_data["user_id"]), actor=request.user,
                                   note=serializer.validated_data["note"])
        return Response(SupervisedUseSerializer(use).data, status=status.HTTP_201_CREATED)


class SupervisedUseEndView(_Base):
    @extend_schema(tags=TAGS, summary="End a supervisee's use", request=SupervisedActionSerializer,
                   responses={200: SupervisedUseSerializer, **CODES})
    def post(self, request, pk):
        use = get_object_or_404(SupervisedUse.objects.select_related("session__machine"), pk=pk)
        _session(request, use.session_id)
        SupervisedActionSerializer(data=request.data).is_valid(raise_exception=True)
        return Response(SupervisedUseSerializer(supervised.end_use(use, actor=request.user)).data)


class SupervisedSessionCloseView(_Base):
    @extend_schema(tags=TAGS, summary="Close the session (ends every open use)", request=SupervisedActionSerializer,
                   responses={200: SupervisedSessionSerializer, **CODES})
    def post(self, request, pk):
        session = _session(request, pk)
        SupervisedActionSerializer(data=request.data).is_valid(raise_exception=True)
        supervised.close_session(session, actor=request.user)
        return Response(_detail(session))
