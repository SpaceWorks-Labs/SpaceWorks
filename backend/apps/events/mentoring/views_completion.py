from django.utils.translation import gettext
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from rest_framework.response import Response
from apps.events.contributions.api_common import AdminView, envelope
from apps.events.contributions.serializers import CommandSerializer, AggregateSerializer, ERRORS
from apps.events.contributions.errors import ProgrammeError
from . import assignment_workflow, import_export
from .serializers import AssignmentMappingSerializer


class AssignmentActivateView(AdminView):
    permission = "manage_team"
    action = "activate"

    @extend_schema(request=CommandSerializer, responses={200: AssignmentMappingSerializer, **ERRORS})
    def post(self, request, pk, assignment_id):
        self.event(request, pk)
        result = assignment_workflow.transition(actor=request.user, event_id=pk, assignment_id=assignment_id,
            payload=self.input(request, CommandSerializer), action=self.action)
        return Response(assignment_workflow.mapping_projection(result.row))


class AssignmentEndView(AssignmentActivateView):
    action = "end"


class TeamExportView(AdminView):
    permission = None

    @extend_schema(parameters=[OpenApiParameter("format", str, enum=["csv", "xlsx"], required=True),
        OpenApiParameter("practice_run_id", OpenApiTypes.UUID)],
        responses={(200, "text/csv"): OpenApiTypes.BINARY,
                   (200, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"): OpenApiTypes.BINARY, **ERRORS})
    def get(self, request, pk):
        from uuid import UUID
        event = self.event(request, pk)
        format = request.query_params.get("format", "csv")
        practice = request.query_params.get("practice_run_id")
        try:
            practice = str(UUID(practice)) if practice else None
        except ValueError as exc:
            raise ProgrammeError("invalid_input", gettext("Use a practice run UUID."), status=400) from exc
        raw, mime = import_export.export_teams(actor=request.user, event=event, format=format, practice_run_id=practice)
        response = HttpResponse(raw, content_type=mime)
        response["Content-Disposition"] = f'attachment; filename="event-{event.pk}-teams.{format}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response
