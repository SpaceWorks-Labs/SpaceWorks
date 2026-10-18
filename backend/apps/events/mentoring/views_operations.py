from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.events.contributions.api_common import AdminView, envelope, paginated, page_schema
from apps.events.contributions.serializers import AggregateSerializer, CommandSerializer, ERRORS
from . import analytics, assignment_workflow, import_workflow, round_workflow, round_management, projections
from .models_queue import MentorTeamAssignment
from .models_rounds import MentorRound
from .serializers import (AssignmentInputSerializer, AssignmentPreviewSerializer, RoundSerializer,
    RoundWriteSerializer, LeaseSerializer, ClaimInputSerializer, LeaseInputSerializer, RoundSubmitSerializer)
from .serializers_operations import (AnalyticsSerializer, ImportPreviewSerializer,
                                    ImportCommitSerializer, ImportResultSerializer, ImportUploadSerializer)


class AssignmentsView(AdminView):
    permission = "manage_team"

    @extend_schema(responses={200: page_schema("MentorTeamAssignmentPage", AggregateSerializer), **ERRORS})
    def get(self, request, pk):
        self.event(request, pk)
        return paginated(request, MentorTeamAssignment.objects.filter(event_id=pk).order_by("pk"), envelope)

    @extend_schema(request=AssignmentInputSerializer, responses={201: AggregateSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = assignment_workflow.assign(actor=request.user, event_id=pk,
            payload=self.input(request, AssignmentInputSerializer))
        return Response(envelope(result.row), status=result.status)


class AssignmentPreviewView(AdminView):
    permission = "manage_team"
    http_method_names = ["post", "options"]

    @extend_schema(request=AssignmentInputSerializer, responses={200: AssignmentPreviewSerializer, **ERRORS})
    def post(self, request, pk):
        event = self.event(request, pk)
        return Response(assignment_workflow.preview(actor=request.user, event=event,
            payload=self.input(request, AssignmentInputSerializer)))


class AssignmentRunView(AssignmentsView):
    http_method_names = ["post", "options"]


class RoundsView(AdminView):
    feature = "events.mentor_rounds"

    @extend_schema(responses={200: page_schema("MentorRoundsPage", RoundSerializer), **ERRORS})
    def get(self, request, pk):
        self.event(request, pk)
        return paginated(request, MentorRound.objects.filter(event_id=pk,
            practice_run_id__isnull=True).order_by("index", "pk"), projections.round_row)

    @extend_schema(request=RoundWriteSerializer, responses={201: RoundSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = round_management.save(actor=request.user, event_id=pk,
            payload=self.input(request, RoundWriteSerializer))
        return Response(projections.round_row(result.row), status=result.status)


class RoundDetailView(RoundsView):
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(responses={200: RoundSerializer, **ERRORS})
    def get(self, request, pk, round_id):
        event = self.event(request, pk)
        row = get_object_or_404(MentorRound, pk=round_id, event_id=pk)
        data = projections.round_row(row)
        from apps.events import event_authority
        if not event_authority.can(request.user, event, None):
            from .round_board import project
            data.update(project(actor=request.user, event=event, round=row))
        return Response(data)

    @extend_schema(request=RoundWriteSerializer, responses={200: RoundSerializer, **ERRORS})
    def patch(self, request, pk, round_id):
        self.event(request, pk)
        result = round_management.save(actor=request.user, event_id=pk, round_id=round_id,
            payload=self.input(request, RoundWriteSerializer))
        return Response(projections.round_row(result.row))


class RoundOpenView(AdminView):
    feature = "events.mentor_rounds"
    permission = "manage_team"
    action = "open"
    http_method_names = ["post", "options"]

    @extend_schema(request=CommandSerializer, responses={200: RoundSerializer, **ERRORS})
    def post(self, request, pk, round_id):
        self.event(request, pk)
        result = round_workflow.transition(actor=request.user, event_id=pk, round_id=round_id,
            payload=self.input(request, CommandSerializer), action=self.action)
        return Response(projections.round_row(result.row))


class RoundCloseView(RoundOpenView):
    action = "close"


class RoundSkipView(RoundOpenView):
    action = "skip"


class RoundVisitView(AdminView):
    feature = "events.mentor_rounds"
    action = "claim"
    serializer = ClaimInputSerializer
    http_method_names = ["post", "options"]

    def execute(self, request, pk, round_id, team_id):
        self.event(request, pk)
        result = round_workflow.visit(actor=request.user, event_id=pk, round_id=round_id, team_id=team_id,
            payload=self.input(request, self.serializer), action=self.action)
        return Response(envelope(result.row) if self.action == "submit" else projections.lease(result.row), status=result.status)


class RoundClaimView(RoundVisitView):
    @extend_schema(request=ClaimInputSerializer, responses={200: LeaseSerializer, **ERRORS})
    def post(self, request, pk, round_id, team_id):
        return self.execute(request, pk, round_id, team_id)


class RoundHeartbeatView(RoundVisitView):
    action = "heartbeat"
    serializer = LeaseInputSerializer

    @extend_schema(request=LeaseInputSerializer, responses={200: LeaseSerializer, **ERRORS})
    def post(self, request, pk, round_id, team_id):
        return self.execute(request, pk, round_id, team_id)


class RoundReleaseView(RoundHeartbeatView):
    action = "release"


class RoundSubmitView(RoundVisitView):
    action = "submit"
    serializer = RoundSubmitSerializer

    @extend_schema(request=RoundSubmitSerializer, responses={201: AggregateSerializer, **ERRORS})
    def post(self, request, pk, round_id, team_id):
        return self.execute(request, pk, round_id, team_id)


class AnalyticsView(AdminView):
    @extend_schema(responses={200: AnalyticsSerializer, **ERRORS})
    def get(self, request, pk):
        event = self.event(request, pk)
        return Response(analytics.summary(actor=request.user, event=event))


def import_projection(row):
    import json
    return {**envelope(row), "preview_token": row.token, "mapping_sha256": row.mapping_sha256,
        "expires_at": row.expires_at, "state": "committed" if row.committed_at else "preview",
        "practice_run_id": row.practice_run_id, "mapping_count": len(json.loads(row.mapping))}


class ImportPreviewView(AdminView):
    permission = "manage_team"

    @extend_schema(request={"application/json": ImportPreviewSerializer,
        "multipart/form-data": ImportUploadSerializer}, responses={201: ImportResultSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        if request.FILES:
            parsed = self.input(request, ImportUploadSerializer)
            file = parsed.pop("file")
            from .import_parser import parse, MAX_BYTES
            parsed["rows"] = parse(file.read(MAX_BYTES + 1), filename=file.name)
        else:
            parsed = self.input(request, ImportPreviewSerializer)
        result = import_workflow.preview(actor=request.user, event_id=pk, payload=parsed)
        return Response(import_projection(result.row), status=result.status)


class ImportCommitView(AdminView):
    permission = "manage_team"

    @extend_schema(request=ImportCommitSerializer, responses={200: ImportResultSerializer, **ERRORS})
    def post(self, request, pk):
        self.event(request, pk)
        result = import_workflow.commit(actor=request.user, event_id=pk,
            payload=self.input(request, ImportCommitSerializer))
        return Response(import_projection(result.row))
