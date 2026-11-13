"""Organizer team reads expose operational roster state, never member answers."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from . import team_moderation
from .api_base import AdminView, ProgrammeCommandThrottle, paginated
from .serializers_commands import TeamMoveInput, TeamRenameInput
from .admission_inputs import CommandInput
from .team_models import HackathonTeam
from apps.events.submissions.views_projects import ERRORS


class OrganizerTeamSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    version = serializers.IntegerField()
    name = serializers.CharField()
    state = serializers.CharField()
    member_count = serializers.IntegerField()
    eligibility_issue = serializers.BooleanField()
    roster_hash = serializers.CharField()
    allowed_actions = serializers.ListField(child=serializers.CharField())


class OrganizerTeamPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = OrganizerTeamSerializer(many=True)


def project(row):
    return {"id": row.pk, "event_id": row.event_id, "version": row.version,
        "name": row.name, "state": row.state, "member_count": row.memberships.filter(state="active").count(),
        "eligibility_issue": row.eligibility_issue, "roster_hash": row.roster_hash, "allowed_actions": []}


class OrganizerTeamListView(AdminView):
    permission = "manage_team"

    @extend_schema(tags=["Event programme teams"], responses={200: OrganizerTeamPageSerializer, **ERRORS})
    def get(self, request, pk):
        event, _ = self.team_admin_target(request, pk)
        return paginated(request, HackathonTeam.objects.filter(event=event).order_by("pk"), project)


class OrganizerTeamMemberSerializer(serializers.Serializer):
    member_id = serializers.IntegerField()
    is_leader = serializers.BooleanField()
    display_name = serializers.CharField(allow_blank=True)


class OrganizerTeamDetailSerializer(OrganizerTeamSerializer):
    members = OrganizerTeamMemberSerializer(many=True)


def project_detail(row):
    """E-F4: the active roster for "move member". Names come only from the member's own team profile."""
    from .team_projection import profile
    members = row.memberships.filter(state="active").order_by("joined_at", "pk")
    return {**project(row), "members": [{"member_id": m.member_id, "is_leader": m.member_id == row.leader_id,
                                         "display_name": (profile(row.event_id, m.member_id) or {}).get("display_name", "")}
                                        for m in members]}


class OrganizerTeamDetailView(AdminView):
    permission = "manage_team"

    @extend_schema(tags=["Event programme teams"], responses={200: OrganizerTeamDetailSerializer, **ERRORS})
    def get(self, request, pk, team_id):
        event, _ = self.team_admin_target(request, pk)
        return Response(project_detail(get_object_or_404(HackathonTeam, event=event, pk=team_id)))


class OrganizerTeamCommandView(AdminView):
    permission = "manage_team"
    throttle_classes = [ProgrammeCommandThrottle]
    serializer = CommandInput
    service = None

    def post(self, request, pk, team_id):
        event, _ = self.team_admin_target(request, pk)
        team = self.service(event_id=event.pk, team_id=team_id, actor=request.user,
                            data=self.command_data(request, self.serializer))
        return Response(project(team))


class OrganizerTeamRenameView(OrganizerTeamCommandView):
    serializer = TeamRenameInput
    service = staticmethod(team_moderation.rename)

    @extend_schema(tags=["Event programme teams"], request=TeamRenameInput, responses={200: OrganizerTeamSerializer, **ERRORS},
                   summary="Organiser renames a team")
    def post(self, request, pk, team_id):
        return super().post(request, pk, team_id)


class OrganizerTeamMoveView(OrganizerTeamCommandView):
    serializer = TeamMoveInput
    service = staticmethod(team_moderation.move_member)

    @extend_schema(tags=["Event programme teams"], request=TeamMoveInput, responses={200: OrganizerTeamSerializer, **ERRORS},
                   summary="Organiser moves a member to another open team")
    def post(self, request, pk, team_id):
        return super().post(request, pk, team_id)


class OrganizerTeamDeleteView(OrganizerTeamCommandView):
    service = staticmethod(team_moderation.delete)

    @extend_schema(tags=["Event programme teams"], request=CommandInput, responses={200: OrganizerTeamSerializer, **ERRORS},
                   summary="Organiser deletes a team; it can be restored for five minutes")
    def post(self, request, pk, team_id):
        return super().post(request, pk, team_id)


class OrganizerTeamRestoreView(OrganizerTeamCommandView):
    service = staticmethod(team_moderation.restore)

    @extend_schema(tags=["Event programme teams"], request=CommandInput, responses={200: OrganizerTeamSerializer, **ERRORS},
                   summary="Undo a team delete inside the five-minute window")
    def post(self, request, pk, team_id):
        return super().post(request, pk, team_id)
