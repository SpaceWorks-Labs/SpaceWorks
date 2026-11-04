"""Organizer team reads expose operational roster state, never member answers."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from .api_base import AdminView, paginated
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
        event, _ = self.admin_target(request, pk)
        return paginated(request, HackathonTeam.objects.filter(event=event).order_by("pk"), project)


class OrganizerTeamDetailView(AdminView):
    permission = "manage_team"

    @extend_schema(tags=["Event programme teams"], responses={200: OrganizerTeamSerializer, **ERRORS})
    def get(self, request, pk, team_id):
        event, _ = self.admin_target(request, pk)
        return Response(project(get_object_or_404(HackathonTeam, event=event, pk=team_id)))
