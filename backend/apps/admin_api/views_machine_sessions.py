"""Staff machine sessions (lane L23, #158.2b): list, start for a member, stop, correct,
assign an unattributed device session, and confirm.

Authority: MANAGE_MACHINES in the space, narrowed by the actor's machine scope (a Machine
Manager sees and acts on the types their role covers; a Space Manager on all). Every
route answers 404 while `machines.sessions` is off. Staff never override certification or
check-in: starting for a member runs the member's own checks.
"""

from django.utils.translation import gettext
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import rbac
from apps.admin_api.list_options import StaffListPagination
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines import access, event_use, sessions_service as service
from apps.machines import sessions_state as state
from apps.machines.models import Machine, MachineSession
from apps.machines.serializers_sessions import (
    SessionAmendSerializer, SessionAssignSerializer, StaffSessionSerializer, StaffSessionStartSerializer,
)
from apps.makerspaces.models import Makerspace
from apps.payments.models import Payment

TAGS = ["Admin machine sessions"]
ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid input."),
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(ErrorSerializer, description="Machine management permission required, or the member "
                                                       "may not use the machine (typed code)."),
    404: OpenApiResponse(description="Not found, or sessions are off in this space."),
    409: OpenApiResponse(ErrorSerializer, description="A typed session conflict (machine_in_use, session_closed, "
                                                       "session_final, session_live, session_unattributed, ...)."),
}
FILTERS = [OpenApiParameter("status", str, enum=["live", "review", "closed"], required=False),
           OpenApiParameter("machine", int, required=False), OpenApiParameter("member", int, required=False),
           OpenApiParameter("machine_type", int, required=False, description="Machine type id (A16)."),
           OpenApiParameter("source", str, enum=["member_qr", "staff", "device"], required=False),
           OpenApiParameter("since", str, required=False, description="ISO date (local), inclusive."),
           OpenApiParameter("until", str, required=False, description="ISO date (local), inclusive.")]


def _space(actor, makerspace_id):
    space = get_object_or_404(rbac.scope_by_visibility_or_action(
        actor, rbac.Action.MANAGE_MACHINES, Makerspace.objects.all(), field="id"), pk=makerspace_id)
    state.require_sessions(space)
    if not rbac.can(actor, rbac.Action.MANAGE_MACHINES, space.pk):
        raise PermissionDenied()
    return space


def _scoped(actor, space):
    machines = access.scope_machines_for_actor(actor, Machine.objects.filter(makerspace=space))
    return event_use.with_event(MachineSession.objects.filter(makerspace=space, machine__in=machines).select_related(
        "makerspace", "machine", "machine_type", "member")).prefetch_related("amendments__actor", "amendments__member")


def _session(actor, pk):
    row = get_object_or_404(MachineSession.objects.select_related("makerspace", "machine"), pk=pk)
    _space(actor, row.makerspace_id)
    if not access.can_manage_machine(actor, row.machine):
        raise PermissionDenied(gettext("This machine is outside your management scope."))
    return row


def _member(space, member_id, *, active=False):
    from apps.accounts.models import User
    from apps.accounts.staff_identity import person_q
    memberships = {"makerspace_memberships__makerspace": space}
    if active:
        memberships["makerspace_memberships__status"] = "active"
    member = User.objects.filter(person_q(), pk=member_id, **memberships).first()
    if member is None:
        raise ValidationError({"member_id": gettext("Choose a member of this makerspace.")})
    return member


def _payments(rows):
    ids = [row.pk for row in rows if row.billable]
    if not ids:
        return {}
    return {payment.subject_id: payment for payment in Payment.objects.filter(
        makerspace_id=rows[0].makerspace_id, subject_type=Payment.SubjectType.MACHINE_SESSION, subject_id__in=ids)}


def render(request, rows, *, many=False):
    listed = list(rows) if many else [rows]
    return StaffSessionSerializer(listed if many else listed[0], many=many,
                                  context={"request": request, "payments": _payments(listed)}).data


def _filter(rows, params, space):
    from apps.makerspaces.local_time import local_day_bounds
    from datetime import date
    status_filter = params.get("status")
    if status_filter == "live":
        rows = rows.filter(ended_at__isnull=True)
    elif status_filter in ("review", "closed"):
        review = Q(ended_at__isnull=False) & (Q(flagged=True) | Q(member__isnull=True)) & ~Q(amendments__kind="confirm")
        rows = rows.filter(review) if status_filter == "review" else rows.filter(ended_at__isnull=False).exclude(review)
    for key, field in (("machine", "machine_id"), ("machine_type", "machine_type_id"), ("member", "member_id")):
        if str(params.get(key, "")).isdigit():
            rows = rows.filter(**{field: int(params[key])})
    if params.get("source") in MachineSession.Source.values:
        rows = rows.filter(source=params["source"])
    try:
        if params.get("since"):
            rows = rows.filter(started_at__gte=local_day_bounds(space, date.fromisoformat(params["since"]))[0])
        if params.get("until"):
            rows = rows.filter(started_at__lt=local_day_bounds(space, date.fromisoformat(params["until"]))[1])
    except ValueError:
        raise ValidationError({"since": gettext("Use YYYY-MM-DD dates.")})
    return rows.distinct()


class MachineSessionListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Machine sessions in this space (live, to review, closed)", parameters=FILTERS,
                   responses={200: StaffSessionSerializer(many=True), **ERRORS})
    def get(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        rows = _filter(_scoped(request.user, space), request.query_params, space).order_by("-started_at", "-pk")
        paginator = StaffListPagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        return paginator.get_paginated_response(render(request, page, many=True))

    @extend_schema(tags=TAGS, summary="Start a session for a member", request=StaffSessionStartSerializer,
                   description="The member must be checked in and certified exactly as when they start it themself.",
                   responses={201: StaffSessionSerializer, **ERRORS})
    def post(self, request, makerspace_id):
        space = _space(request.user, makerspace_id)
        payload = StaffSessionStartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        machine = get_object_or_404(access.scope_machines_for_actor(request.user, Machine.objects.select_related(
            "makerspace", "machine_type").filter(makerspace=space, is_active=True)), pk=payload.validated_data["machine_id"])
        if not access.can_manage_machine(request.user, machine):
            raise PermissionDenied(gettext("This machine is outside your management scope."))
        member = _member(space, payload.validated_data["member_id"])
        with transaction.atomic():
            row = service.start(machine, member, actor=request.user, source=MachineSession.Source.STAFF)
            event_use.manage(request.user, row, payload.validated_data["event_id"])  # decision 342
        return Response(render(request, _scoped(request.user, space).get(pk=row.pk)), status=status.HTTP_201_CREATED)


class _SessionAction(APIView):
    permission_classes = [IsActiveStaff]

    def done(self, request, row):
        return Response(render(request, _scoped(request.user, row.makerspace).get(pk=row.pk)))


class MachineSessionStopView(_SessionAction):
    @extend_schema(tags=TAGS, summary="Stop a live session", request=None,
                   responses={200: StaffSessionSerializer, **ERRORS})
    def post(self, request, pk):
        row = _session(request.user, pk)
        service.stop(row, actor=request.user, reason=MachineSession.StopReason.STAFF)
        return self.done(request, row)


class MachineSessionAmendView(_SessionAction):
    @extend_schema(tags=TAGS, summary="Correct an auto-stopped session's duration (before confirming)",
                   request=SessionAmendSerializer, responses={200: StaffSessionSerializer, **ERRORS})
    def post(self, request, pk):
        row = _session(request.user, pk)
        payload = SessionAmendSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        service.amend(row, request.user, **payload.validated_data)
        return self.done(request, row)


class MachineSessionAssignView(_SessionAction):
    @extend_schema(tags=TAGS, summary="Assign an unattributed device session to a member",
                   request=SessionAssignSerializer, responses={200: StaffSessionSerializer, **ERRORS})
    def post(self, request, pk):
        row = _session(request.user, pk)
        payload = SessionAssignSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        member = _member(row.makerspace, payload.validated_data["member_id"], active=True)
        service.assign(row, request.user, member=member, reason=payload.validated_data["reason"])
        return self.done(request, row)


class MachineSessionConfirmView(_SessionAction):
    @extend_schema(tags=TAGS, summary="Confirm a session under review: it becomes final and its charge is raised",
                   description="The charge is a PENDING ledger entry at the rate frozen when the session started; "
                               "staff settle or waive it through the usual payment path.",
                   request=None, responses={200: StaffSessionSerializer, **ERRORS})
    def post(self, request, pk):
        row = _session(request.user, pk)
        service.confirm(row, request.user)
        return self.done(request, row)
