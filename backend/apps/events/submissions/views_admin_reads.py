"""Paginated organizer indexes omit member answers and raw storage locators."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from apps.events.hackathons.api_base import AdminView, paginated
from apps.events.submissions.ports import boundary
from apps.events.submissions.models_projects import HackathonSubmission
from apps.events.submissions.views_projects import ERRORS


class OrganizerProjectSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    event_id = serializers.IntegerField()
    team_id = serializers.IntegerField()
    team_name = serializers.CharField()
    version = serializers.IntegerField()
    state = serializers.CharField()
    title = serializers.CharField()
    snapshot_id = serializers.IntegerField(allow_null=True)
    triage = serializers.CharField()
    allowed_actions = serializers.ListField(child=serializers.CharField())
    assets = serializers.ListField(child=serializers.DictField())


class OrganizerProjectPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = OrganizerProjectSerializer(many=True)


def project(row):
    return {"id": row.pk, "event_id": row.event_id, "team_id": row.team_id,
        "team_name": row.team.name, "version": row.version, "state": row.state,
        "title": row.title, "snapshot_id": row.current_snapshot_id, "triage": row.triage,
        "allowed_actions": ["triage"]+(["amend"] if row.current_snapshot_id and row.state not in ("withdrawn", "disqualified") else []),
        "assets": [{"id": asset.pk, "state": asset.state, "kind": asset.kind,
            "bytes": asset.actual_bytes, "mime": asset.canonical_mime, "sha256": asset.sha256,
            "download_url": f"/api/v1/admin/events/{row.event_id}/assets/{asset.pk}/download/"}
            for asset in row.assets.filter(pk__in=row.asset_ids).order_by("pk")[:100]]}


class OrganizerProjectListView(AdminView):
    permission = "manage_hackathon"

    @extend_schema(tags=["Event submissions"], responses={200: OrganizerProjectPageSerializer, **ERRORS})
    def get(self, request, pk):
        with boundary().locked(actor=request.user, event_id=pk, team_id=None, action="admin_read"):
            rows = HackathonSubmission.objects.filter(event_id=pk).select_related("team").order_by("pk")
            return paginated(request, rows, project)


class OrganizerProjectDetailView(AdminView):
    permission = "manage_hackathon"

    @extend_schema(tags=["Event submissions"], responses={200: OrganizerProjectSerializer, **ERRORS})
    def get(self, request, pk, submission_id):
        from rest_framework.response import Response
        with boundary().locked(actor=request.user, event_id=pk, team_id=None, action="admin_read"):
            return Response(project(get_object_or_404(HackathonSubmission.objects.select_related("team"),
                event_id=pk, pk=submission_id)))
