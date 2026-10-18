from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from datetime import timedelta

from .errors import SubmissionError
from .models_projects import HackathonSubmission
from .ports import boundary
from .project_validation import PROJECT_FIELDS
from .serializers import (CommandSerializer, ProjectPatchSerializer, ProjectResponseSerializer,
                          AmendSerializer, TriageSerializer, ErrorSerializer)
from .workflow import command
from .moderation import triage

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 409, 410, 413, 423, 429, 503)}


class ProjectView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProjectResponseSerializer, **ERRORS}, tags=["Event submissions"])
    def get(self, request, pk, team_id, **kwargs):
        with boundary().locked(actor=request.user, event_id=pk, team_id=team_id, action="project_read") as ctx:
            project = HackathonSubmission.objects.filter(event_id=pk, team_id=team_id).first()
            if project is None:
                return Response({"id": None, "event_id": pk, "version": 0, "state": "draft",
                                 "snapshot_id": None, "project": {}, "allowed_actions": ["save"]})
            document = {key: getattr(project, key) for key in PROJECT_FIELDS}
            document["links"] = list(project.links.filter(version=project.links_version).values("kind", "url", "public_requested"))
            actions = []
            if request.user.pk in ctx.member_ids:
                if project.state in {"draft", "submitted"}:
                    if timezone.now() <= ctx.deadline + timedelta(seconds=ctx.grace_seconds):
                        actions.append("save")
                    if request.user.pk == ctx.leader_id:
                        actions.append("submit")
                if project.state != "withdrawn":
                    actions.append("withdraw")
            return Response({"id": project.pk, "event_id": pk, "version": project.version, "state": project.state,
                             "snapshot_id": project.current_snapshot_id, "project": document,
                             "allowed_actions": actions})

    @extend_schema(request=ProjectPatchSerializer, responses={200: ProjectResponseSerializer, **ERRORS}, tags=["Event submissions"])
    def patch(self, request, pk, team_id, **kwargs):
        serializer = ProjectPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        operation, expected = str(data.pop("operation_id")), data.pop("expected_version")
        return Response(command(actor=request.user, event_id=pk, team_id=team_id, action="save",
                                operation_id=operation, expected_version=expected, data=data))


class ProjectCommandView(APIView):
    permission_classes = [IsAuthenticated]
    action = "submit"

    @extend_schema(request=CommandSerializer, responses={200: ProjectResponseSerializer, **ERRORS}, tags=["Event submissions"])
    def post(self, request, pk, team_id, **kwargs):
        serializer = CommandSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(command(actor=request.user, event_id=pk, team_id=team_id, action=self.action,
                                **serializer.validated_data))


class AmendView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AmendSerializer, responses={200: ProjectResponseSerializer, **ERRORS}, tags=["Event submissions"])
    def post(self, request, pk, submission_id):
        serializer = AmendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Resolve exact event/permission before resolving a nested team identity.
        with boundary().locked(actor=request.user, event_id=pk, team_id=None, action="amend"):
            project = HackathonSubmission.objects.filter(pk=submission_id, event_id=pk).first()
            if project is None:
                raise SubmissionError("not_found", 404)
            team_id = project.team_id
        data = dict(serializer.validated_data)
        return Response(command(actor=request.user, event_id=pk, team_id=team_id, action="amend",
            operation_id=str(data.pop("operation_id")), expected_version=data.pop("expected_version"), data=data))


class TriageView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=TriageSerializer, responses={200: ProjectResponseSerializer, **ERRORS}, tags=["Event submissions"])
    def post(self, request, pk, submission_id):
        serializer = TriageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(triage(actor=request.user, event_id=pk, submission_id=submission_id, **serializer.validated_data))
