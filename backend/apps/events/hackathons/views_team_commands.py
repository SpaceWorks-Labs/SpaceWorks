"""Each team action has one literal named route and a closed serializer."""
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema
from rest_framework.response import Response
from . import team_invitations, team_lifecycle
from .api_base import MemberCommandView
from .api_schema import AggregateSerializer, ERRORS, InviteSerializer, TeamSerializer
from .serializers_commands import AcceptInput, InviteInput, WithdrawalInput
from .admission_inputs import CommandInput
from .team_projection import project_team


def summary(team):
    return {"id": team.pk, "event_id": team.event_id, "version": team.version,
            "state": team.state, "allowed_actions": []}


class InviteView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=InviteInput, responses={200: PolymorphicProxySerializer(component_name="ProgrammeInviteResult", serializers=[InviteSerializer, AggregateSerializer], resource_type_field_name=None), **ERRORS})
    def post(self, request, makerspace_id, pk, team_id):
        self.member_target(request, makerspace_id, pk)
        row, token = team_invitations.invite(event_id=pk, team_id=team_id, actor=request.user, data=self.command_data(request, InviteInput))
        if row is None:
            from .team_models import HackathonTeam
            team = HackathonTeam.objects.get(pk=team_id, event_id=pk)
            return Response({"id": team.pk, "event_id": pk, "version": team.version, "state": "revoked", "allowed_actions": []})
        return Response({"id": row.pk, "team_id": team_id, "team_version": row.team.version,
                         "token": token, "expires_at": row.expires_at})


class JoinRequestView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=CommandInput, responses={200: AggregateSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk, team_id):
        self.member_target(request, makerspace_id, pk)
        team = team_invitations.join_request(event_id=pk, team_id=team_id, actor=request.user, data=self.command_data(request, CommandInput))
        return Response(summary(team))


class AcceptView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=AcceptInput, responses={200: TeamSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk, team_id):
        event, config = self.member_target(request, makerspace_id, pk)
        team = team_invitations.accept(event_id=pk, team_id=team_id, actor=request.user, data=self.command_data(request, AcceptInput))
        return Response(project_team(team, actor=request.user, config=config))


class LeaveView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=CommandInput, responses={200: AggregateSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk, team_id):
        self.member_target(request, makerspace_id, pk)
        team = team_lifecycle.leave(event_id=pk, team_id=team_id, actor=request.user, data=self.command_data(request, CommandInput))
        return Response(summary(team))


class CancelView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=WithdrawalInput, responses={200: AggregateSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk, team_id):
        self.member_target(request, makerspace_id, pk)
        team = team_lifecycle.leave(event_id=pk, team_id=team_id, actor=request.user,
            data=self.command_data(request, WithdrawalInput), cancel=True)
        return Response(summary(team))


class LockView(MemberCommandView):
    @extend_schema(tags=["Event teams"], request=CommandInput, responses={200: TeamSerializer, **ERRORS})
    def post(self, request, makerspace_id, pk, team_id):
        event, config = self.member_target(request, makerspace_id, pk)
        team = team_lifecycle.lock(event_id=pk, team_id=team_id, actor=request.user, data=self.command_data(request, CommandInput))
        return Response(project_team(team, actor=request.user, config=config))
