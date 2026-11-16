from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.events.contributions.api_common import AdminView, envelope, paginated, page_schema
from apps.events.contributions.serializers import AggregateSerializer, ERRORS
from .serializers_configuration import (MentorProfileWriteSerializer, MentorProfileSerializer,
    HelpTypeWriteSerializer, HelpTypeSerializer, ConflictWriteSerializer, MuteSerializer,
    NominationSerializer, RenewHelpSerializer, ConflictSerializer, MuteResultSerializer)
from .models_queue import MentorProfile, EventHelpType
from . import configuration_workflow as workflow, help_workflow, projections


def profile(row):
    return {**envelope(row), "state": "active", **{key: getattr(row, key) for key in (
        "assignment_id", "skills", "availability", "affiliation", "max_active_teams")}}


def category(row):
    return {**envelope(row), "state": "active", **{key: getattr(row, key) for key in (
        "key", "label", "skill_tags", "priority", "open_limit", "claim_minutes", "expiry_minutes", "organizer_contact_action")}}


class MentorProfileView(AdminView):
    @extend_schema(responses={200: MentorProfileSerializer, **ERRORS})
    def get(self, request, pk, assignment_id):
        event = self.event(request, pk)
        row = get_object_or_404(MentorProfile, event=event, assignment_id=assignment_id)
        from apps.events import event_authority
        if row.assignment.member_id != request.user.pk:
            event_authority.require(request.user, event, "manage_team")
        return Response(profile(row))

    @extend_schema(request=MentorProfileWriteSerializer, responses={200: MentorProfileSerializer, **ERRORS})
    def patch(self, request, pk, assignment_id):
        self.event(request, pk)
        result = workflow.save_profile(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, MentorProfileWriteSerializer))
        return Response(profile(result.row))


class HelpTypesView(AdminView):
    permission = "manage_team"

    @extend_schema(responses={200: page_schema("HelpTypesPage", HelpTypeSerializer), **ERRORS})
    def get(self, request, pk):
        self.event(request, pk)
        return paginated(request, EventHelpType.objects.filter(event_id=pk).order_by("pk"), category)

    @extend_schema(request=HelpTypeWriteSerializer, responses={201: HelpTypeSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = workflow.save_help_type(actor=request.user, event_id=pk,
            payload=self.input(request, HelpTypeWriteSerializer))
        return Response(category(result.row), status=result.status)


class HelpTypeDetailView(HelpTypesView):
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(responses={200: HelpTypeSerializer, **ERRORS})
    def get(self, request, pk, type_id):
        self.event(request, pk)
        return Response(category(get_object_or_404(EventHelpType, event_id=pk, pk=type_id)))

    @extend_schema(request=HelpTypeWriteSerializer, responses={200: HelpTypeSerializer, **ERRORS})
    def patch(self, request, pk, type_id):
        self.event(request, pk)
        result = workflow.save_help_type(actor=request.user, event_id=pk, type_id=type_id,
            payload=self.input(request, HelpTypeWriteSerializer))
        return Response(category(result.row))


class ConflictView(AdminView):
    @extend_schema(responses={200: page_schema("MentorConflictsPage", ConflictSerializer), **ERRORS})
    def get(self, request, pk):
        event = self.event(request, pk)
        from .models_rounds import MentorConflict
        from . import policy
        rows = MentorConflict.objects.filter(event=event)
        if not policy.queue_manager(request.user, event):
            mentor, _ = policy.mentor_for(request.user, event, on_shift=False)
            rows = rows.filter(mentor=mentor)
        return paginated(request, rows.order_by("pk"), self.project)

    @staticmethod
    def project(row):
        return {**envelope(row), "state": "active" if row.active else "ended", "active": row.active,
            "kind": row.kind, "mentor_assignment_id": row.mentor_id, "team_id": row.team_id, "reason": row.reason}

    @extend_schema(request=ConflictWriteSerializer, responses={200: ConflictSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = workflow.conflict(actor=request.user, event_id=pk, payload=self.input(request, ConflictWriteSerializer))
        return Response(self.project(result.row))


class MuteView(AdminView):
    feature = "events.mentor_rounds"

    @extend_schema(request=MuteSerializer, responses={200: MuteResultSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = workflow.mute(actor=request.user, event_id=pk, payload=self.input(request, MuteSerializer))
        return Response({**envelope(result.row), "state": "muted" if result.row.muted_until else "active",
            "muted_until": result.row.muted_until})


class NominationView(AdminView):
    feature = "events.mentor_rounds"

    @extend_schema(request=NominationSerializer, responses={201: AggregateSerializer, **ERRORS})
    def post(self, request, pk, round_id):
        self.event(request, pk)
        result = workflow.nominate(actor=request.user, event_id=pk, round_id=round_id,
            payload=self.input(request, NominationSerializer))
        return Response({**envelope(result.row), "state": "recorded"}, status=result.status)


class RenewHelpView(AdminView):
    @extend_schema(request=RenewHelpSerializer, responses={200: AggregateSerializer, **ERRORS})
    def post(self, request, pk, help_id):
        event = self.event(request, pk)
        result = help_workflow.command(actor=request.user, event_id=pk, help_id=help_id,
            payload=self.input(request, RenewHelpSerializer), action="renew")
        return Response(projections.help_request(result.row, actor=request.user, event=event, detail=True))
