"""The member's machine sessions (lane L23, #158.2a): scan, see the rate, Start, Stop.

The machine's QR opens `/m/<slug>/machines/<id>/use`; these routes behind it are the
member's own. Every route answers 404 while `machines.sessions` is off for the machine's
space. A claim session (a kiosk walk-in claim) never starts or stops a machine.
"""

from django.utils.translation import gettext
from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.account_kind_guards import require_member_account
from apps.apiclients.throttling import MemberPrincipalRateThrottle
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines import sessions_billing as billing
from apps.machines import sessions_service as service
from apps.machines import sessions_state as state
from apps.machines.models import Machine, MachineSession
from apps.machines.serializers_sessions import (
    MemberSessionSerializer, SessionPreviewSerializer, SessionStartSerializer, rate_payload,
)
from apps.machines.sessions_rules import refusal

TAGS = ["Member machine sessions"]
ERRORS = {
    400: OpenApiResponse(ErrorSerializer, description="Invalid input."),
    401: OpenApiResponse(description="Sign in first."),
    403: OpenApiResponse(ErrorSerializer, description="member_restricted, membership_required, "
                                                       "waiver_acceptance_required or certification_required."),
    404: OpenApiResponse(description="No such machine or session, or sessions are off in this space."),
    409: OpenApiResponse(ErrorSerializer, description="presence_required, machine_unavailable, machine_locked_out, "
                                                       "machine_booked, booking_required, machine_in_use, "
                                                       "session_already_live, session_closed or price_changed."),
}


def _member(request):
    if getattr(request, "claim_session", None) is not None:
        raise PermissionDenied(gettext("Claim sessions cannot use machines."))
    require_member_account(request.user)
    return request.user


def _machine(user, machine_id):
    from apps.makerspaces.models import MakerspaceMembership
    from apps.makerspaces.servability import servable_queryset
    machine = servable_queryset(Machine.objects.select_related("makerspace", "machine_type").filter(
        pk=machine_id, is_active=True), relation="makerspace").first()
    # Members of this space only (any membership state): a stranger learns nothing.
    if machine is None or not MakerspaceMembership.objects.filter(user=user, makerspace_id=machine.makerspace_id).exists():
        raise NotFound()
    state.require_sessions(machine.makerspace)
    return machine


def _render(rows, *, many=False):
    rows = list(rows) if many else [rows]
    payments = {}
    for row in rows:
        payment = billing.payment_for(row) if row.billable and row.ended_at else None
        if payment is not None:
            payments[row.pk] = payment
    serializer = MemberSessionSerializer(rows if many else rows[0], many=many, context={"payments": payments})
    return serializer.data


def _owned(user, pk):
    row = MachineSession.objects.select_related("makerspace", "machine", "machine_type").prefetch_related(
        "amendments").filter(pk=pk, member=user).first()
    if row is None or not state.sessions_on(row.makerspace):
        raise NotFound()
    return row


class _MemberView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [MemberPrincipalRateThrottle]


class MemberSessionPreviewView(_MemberView):
    throttle_scope = "request_status"

    @extend_schema(tags=TAGS, summary="What starting a session on this machine means for me",
                   description="The frozen hourly rate, minimum and maximum length, closing time, and whether I "
                               "may start now (with the typed refusal when not).",
                   responses={200: SessionPreviewSerializer, **ERRORS})
    def get(self, request, machine_id):
        from apps.machines.job_policy import policy_for
        from apps.makerspaces.opening_hours import closing_time
        user = _member(request)
        machine = _machine(user, machine_id)
        active = billing.billing_active(machine.makerspace)
        rate = billing.start_quote(machine, user) if active else None
        problem = refusal(machine, user)
        live = MachineSession.objects.filter(machine=machine, member=user, ended_at__isnull=True).first()
        data = {"machine_id": machine.pk, "machine_name": machine.name, "machine_type_name": machine.machine_type.name,
                "machine_status": machine.status, "billing": bool(rate is not None and rate.total > 0),
                "rate": rate_payload(rate.to_snapshot()) if rate is not None else None,
                "digest": rate.digest if rate is not None else "",
                "max_minutes": policy_for(machine.makerspace, machine.machine_type).session_max_minutes,
                "closes_at": closing_time(machine.makerspace, timezone.now()), "can_start": problem is None,
                "refusal": problem, "live_session": None}
        body = SessionPreviewSerializer(data).data
        body["live_session"] = _render(live) if live is not None else None
        response = Response(body)
        response["Cache-Control"] = "no-store"
        return response


class MemberSessionStartView(_MemberView):
    throttle_scope = "public_request_submit"

    @extend_schema(tags=TAGS, summary="Start a session on this machine", request=SessionStartSerializer,
                   responses={201: MemberSessionSerializer, **ERRORS})
    def post(self, request, machine_id):
        user = _member(request)
        machine = _machine(user, machine_id)
        payload = SessionStartSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        row = service.start(machine, user, actor=user, source=MachineSession.Source.MEMBER_QR,
                            digest=payload.validated_data["digest"] or None)
        return Response(_render(_owned(user, row.pk)), status=status.HTTP_201_CREATED)


class MemberSessionStopView(_MemberView):
    throttle_scope = "public_request_submit"

    @extend_schema(tags=TAGS, summary="Stop my session", request=None,
                   responses={200: MemberSessionSerializer, **ERRORS})
    def post(self, request, pk):
        user = _member(request)
        row = _owned(user, pk)
        service.stop(row, actor=user, reason=MachineSession.StopReason.MEMBER)
        return Response(_render(_owned(user, pk)))


class MemberSessionListView(_MemberView):
    throttle_scope = "request_status"

    @extend_schema(tags=TAGS, summary="My machine sessions, newest first",
                   parameters=[OpenApiParameter("makerspace", int, required=False),
                               OpenApiParameter("live", bool, required=False)],
                   responses={200: MemberSessionSerializer(many=True), **ERRORS})
    def get(self, request):
        from apps.makerspaces.servability import servable_queryset
        user = _member(request)
        rows = servable_queryset(MachineSession.objects.select_related(
            "makerspace", "machine", "machine_type").prefetch_related("amendments").filter(member=user),
            relation="makerspace").filter(makerspace__enabled_features__contains=[state.FEATURE])
        if (space := request.query_params.get("makerspace")) and str(space).isdigit():
            rows = rows.filter(makerspace_id=int(space))
        if request.query_params.get("live") in ("1", "true"):
            rows = rows.filter(Q(ended_at__isnull=True))
        rows = [row for row in rows.order_by("-started_at", "-pk")[:100] if state.sessions_on(row.makerspace)]
        response = Response(_render(rows, many=True))
        response["Cache-Control"] = "no-store"
        return response
