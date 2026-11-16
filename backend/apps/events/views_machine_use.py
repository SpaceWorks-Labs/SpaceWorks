"""Machine use logged with an event (decision 342): the pickers and the area manager's set/clear route.

* Member: the events I may say a job or session is for (own space only).
* Staff: read or set the event of one session or service request. Space Managers and Machine Managers
  within machine scope only; every change is audited with before and after.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.account_kind_guards import require_member_account
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from apps.makerspaces.guards import require_module
from apps.makerspaces.models import Makerspace, MakerspaceMembership
from apps.makerspaces.servability import servable_queryset

from . import machine_use_services as services
from .machine_use_eligibility import eligible_events, linkable_events

TAGS = ["Machine use for events"]
LIMIT = 100


class MachineUseEventOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(allow_null=True)


class MachineEventSerializer(serializers.Serializer):
    event = MachineUseEventOptionSerializer(allow_null=True)
    source = serializers.CharField(allow_blank=True)
    locked = serializers.BooleanField(help_text="True once the organiser approved the cost for the event.")
    options = MachineUseEventOptionSerializer(many=True)


class MachineEventWrite(serializers.Serializer):
    event_id = serializers.IntegerField(min_value=1, allow_null=True,
                                        help_text="An open event of this makerspace; null clears the link.")


def _options(rows):
    return [{"id": e.pk, "title": e.title, "starts_at": e.starts_at, "ends_at": e.ends_at} for e in list(rows)[:LIMIT]]


class MemberMachineUseEventsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=TAGS, summary="Events I may log machine use for", responses={
        200: MachineUseEventOptionSerializer(many=True), **PUBLIC_ERROR_RESPONSES})
    def get(self, request, makerspace_id):
        user = request.user
        if getattr(request, "claim_session", None) is not None:
            raise NotFound()
        require_member_account(user)
        space = get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=makerspace_id)
        if not MakerspaceMembership.objects.filter(user=user, makerspace=space).exists():
            raise NotFound()
        response = Response(_options(eligible_events(user, space)))
        response["Cache-Control"] = "no-store"
        return response


class AdminMachineUseOptionsView(APIView):
    """Open events of this makerspace a staff member may tag a machine booking with (booking create form)."""
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Open events staff can log machine use for", responses={
        200: MachineUseEventOptionSerializer(many=True), **PUBLIC_ERROR_RESPONSES})
    def get(self, request, makerspace_id):
        from apps.accounts import rbac
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        require_module(space, "machines")
        if not any(rbac.can(request.user, action, space.pk)
                   for action in (rbac.Action.MANAGE_MACHINES, rbac.Action.MANAGE_BOOKINGS)):
            raise NotFound()
        return Response(_options(linkable_events(space).order_by("starts_at", "id")))


def _subject(space, kind, pk):
    from apps.machines.models import MachineServiceRequest, MachineSession
    if kind == "session":
        return get_object_or_404(MachineSession.objects.select_related("machine", "machine_type", "member"),
                                 pk=pk, makerspace=space)
    if kind == "request":
        return get_object_or_404(MachineServiceRequest.objects.select_related(
            "queue__machine_type", "bucket__machine__machine_type", "member", "requester", "assigned_machine"),
            pk=pk, makerspace=space)
    if kind == "booking":
        from apps.bookings.models import Booking
        return get_object_or_404(Booking.objects.select_related(
            "space__machine__machine_type", "space__machine_type", "space__makerspace", "member"),
            pk=pk, space__makerspace=space)
    raise NotFound()


def _payload(space, subject):
    from .machine_use_costs import latest_decision
    link = services.current_link(subject)
    decision = latest_decision(link) if link else None
    return {"event": _options([link.event])[0] if link else None, "source": link.source if link else "",
            "locked": bool(decision and decision.decision == "approved"),
            "options": _options(linkable_events(space).order_by("starts_at", "id"))}


class AdminMachineUseEventView(APIView):
    permission_classes = [IsActiveStaff]

    def _resolve(self, request, makerspace_id, kind, pk):
        space = get_object_or_404(Makerspace, pk=makerspace_id)
        require_module(space, "machines")
        subject = _subject(space, kind, pk)
        if not services.may_manage(request.user, subject):
            raise NotFound()
        return space, subject

    @extend_schema(tags=TAGS, summary="The event a session or job is logged for", responses={
        200: MachineEventSerializer, **PUBLIC_ERROR_RESPONSES})
    def get(self, request, makerspace_id, kind, pk):
        space, subject = self._resolve(request, makerspace_id, kind, pk)
        return Response(_payload(space, subject))

    @extend_schema(tags=TAGS, summary="Set, change or clear the event of a session or job",
                   description="Space Manager or Machine Manager within machine scope. Audited with before and "
                               "after; refused while the organiser's cost approval stands.",
                   request=MachineEventWrite, responses={200: MachineEventSerializer, **PUBLIC_ERROR_RESPONSES})
    def put(self, request, makerspace_id, kind, pk):
        space, subject = self._resolve(request, makerspace_id, kind, pk)
        data = MachineEventWrite(data=request.data)
        data.is_valid(raise_exception=True)
        services.manage(request.user, subject, data.validated_data["event_id"])
        return Response(_payload(space, subject))
