"""Member team reads and edits; an ID never replaces active roster authority."""
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from . import team_workflow
from .api_base import MemberCommandView, paginated
from .api_schema import ERRORS, TeamSerializer, paginated_schema
from .serializers_commands import TeamInput
from .team_models import HackathonTeam
from .team_projection import project_team, require_own_team


class TeamListView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=None, responses={200: paginated_schema("ProgrammeTeamPage", TeamSerializer), **ERRORS})
    def get(self, request, makerspace_id, pk):
        event, config = self.team_target(request, makerspace_id, pk)
        rows = HackathonTeam.objects.filter(event=event, memberships__member=request.user, memberships__state="active").order_by("pk")
        return paginated(request, rows, lambda team: project_team(team, actor=request.user, config=config))

    @extend_schema(tags=["Event teams"], request=TeamInput, responses={201: TeamSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk):
        event, config = self.team_target(request, makerspace_id, pk)
        team = team_workflow.create(event_id=pk, actor=request.user, data=self.command_data(request, TeamInput))
        return Response(project_team(team, actor=request.user, config=config), status=201)


class TeamDetailView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=None, responses={200: TeamSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk, team_id):
        event, config = self.team_target(request, makerspace_id, pk)
        team = require_own_team(event_id=pk, team_id=team_id, actor=request.user)
        return Response(project_team(team, actor=request.user, config=config))

    @extend_schema(tags=["Event teams"], request=TeamInput, responses={200: TeamSerializer, **ERRORS})
    def patch(self, request, makerspace_id, pk, team_id):
        event, config = self.team_target(request, makerspace_id, pk)
        team = team_workflow.update(event_id=pk, team_id=team_id, actor=request.user, data=self.command_data(request, TeamInput))
        return Response(project_team(team, actor=request.user, config=config))
