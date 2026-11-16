"""Integrity information for one submission (G10): judges and organisers, read-only.

Information only (#8): the response never carries a verdict, a score or an action, and a
flag never hides or disqualifies anything. 404 while `events.submission_integrity` is off.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.makerspaces.platform import feature_enabled

from .models_projects import HackathonSubmission, SubmissionIntegrityFlag
from .views_projects import ERRORS

RULE_TEXT = {"github_commit_before_kickoff": "The repository has commits dated before kickoff."}


class IntegrityFlagSerializer(serializers.Serializer):
    rule_key = serializers.CharField()
    message = serializers.CharField()
    severity = serializers.ChoiceField(choices=("informational",))
    checked_at = serializers.DateTimeField()


class SubmissionIntegritySerializer(serializers.Serializer):
    submission_id = serializers.IntegerField()
    snapshot_id = serializers.IntegerField(allow_null=True)
    check_state = serializers.ChoiceField(choices=(
        "not_checked", "pending", "clear", "flagged", "no_repository", "unavailable"))
    flags = IntegrityFlagSerializer(many=True)


def integrity_event(actor, pk):
    event = event_authority.get_event(actor, pk, event_authority.VIEW)
    if not (event_authority.can(actor, event, "manage_hackathon") or event_authority.can(actor, event, "judge")):
        raise PermissionDenied()
    if not feature_enabled(event.makerspace, "events.submission_integrity"):
        raise NotFound()
    return event


class FlaggedSnapshotSerializer(serializers.Serializer):
    snapshot_id = serializers.IntegerField()
    submission_id = serializers.IntegerField()
    rule_keys = serializers.ListField(child=serializers.CharField())


class FlaggedSnapshotListSerializer(serializers.Serializer):
    results = FlaggedSnapshotSerializer(many=True)


class SubmissionIntegrityListView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event submissions"], responses={200: FlaggedSnapshotListSerializer, **ERRORS},
                   description="Snapshots of this event that carry an informational integrity flag "
                               "(at most 500). Information only; nothing is hidden or disqualified.")
    def get(self, request, pk):
        event = integrity_event(request.user, pk)
        grouped = {}
        rows = (SubmissionIntegrityFlag.objects.filter(snapshot__submission__event=event)
                .values_list("snapshot_id", "snapshot__submission_id", "rule_key").order_by("snapshot_id", "pk")[:500])
        for snapshot_id, submission_id, rule_key in rows:
            grouped.setdefault(snapshot_id, {"snapshot_id": snapshot_id, "submission_id": submission_id,
                                             "rule_keys": []})["rule_keys"].append(rule_key)
        response = Response({"results": list(grouped.values())})
        response["Cache-Control"] = "private, no-store"
        return response


class SubmissionIntegrityView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Event submissions"], responses={200: SubmissionIntegritySerializer, **ERRORS},
                   description="Informational GitHub first-commit signal for judges and organisers. "
                               "It never disqualifies, hides or scores a project.")
    def get(self, request, pk, submission_id):
        event = integrity_event(request.user, pk)
        submission = get_object_or_404(HackathonSubmission, event=event, pk=submission_id)
        snapshot_id = submission.current_snapshot_id
        check = None
        flags = []
        if snapshot_id:
            from apps.events.models_r2_l2 import SubmissionIntegrityCheck
            check = SubmissionIntegrityCheck.objects.filter(snapshot_id=snapshot_id).first()
            flags = [{"rule_key": row.rule_key, "message": RULE_TEXT.get(row.rule_key, "Information for judges."),
                      "severity": row.severity, "checked_at": row.checked_at}
                     for row in SubmissionIntegrityFlag.objects.filter(snapshot_id=snapshot_id).order_by("pk")]
        response = Response({"submission_id": submission.pk, "snapshot_id": snapshot_id,
                             "check_state": check.state if check else "not_checked", "flags": flags})
        response["Cache-Control"] = "private, no-store"
        return response
