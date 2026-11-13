"""`applications:read` (lane L21a): signed server reads of application COUNTS per event.

HMAC server clients only, bound to their tenant, behind `events.api_read` and an admission
switch (`events.applications` or `events.hackathons`). Each row is one event with counts
by status and by review stage. No application, applicant, answer, score or reviewer
identity ever leaves.
"""
from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from apps.apiclients.read_contract import SignedReadView, keyset_page
from apps.apiclients.scope_registry_reads import APPLICATION_READ
from apps.makerspaces.platform import feature_enabled, module_enabled
from apps.makerspaces.servability import is_servable

from .hackathons.admission_feature import admission_enabled
from .models import Event, HackathonApplication
from .views_integration import ERRORS, PAGE_PARAMETERS

STATES = ("submitted", "offered", "waitlisted", "confirmed", "rejected", "declined", "expired", "withdrawn")


class ApplicationStageCountSerializer(serializers.Serializer):
    stage_id = serializers.IntegerField()
    position = serializers.IntegerField()
    name = serializers.CharField()
    standing = serializers.IntegerField()


class ApplicationCountsSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    total = serializers.IntegerField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    stages = ApplicationStageCountSerializer(many=True)


class ApplicationCountsPageSerializer(serializers.Serializer):
    next_cursor = serializers.CharField(allow_null=True)
    results = ApplicationCountsSerializer(many=True)


def counts(event):
    from .hackathons.admission_stages import current_stage, stages_for
    rows = HackathonApplication.objects.filter(event=event).exclude(state="draft")
    by_status = {state: 0 for state in STATES}
    for row in rows.values("state").annotate(n=Count("pk")):
        by_status[row["state"]] = row["n"]
    stages = list(stages_for(event.pk))
    standing = {stage.pk: 0 for stage in stages}
    if stages:
        for application in rows.filter(state__in=("submitted", "waitlisted")):
            stage = current_stage(application)
            if stage is not None:
                standing[stage.pk] += 1
    return {"event_id": event.pk, "total": sum(by_status.values()), "by_status": by_status,
            "stages": [{"stage_id": s.pk, "position": s.position, "name": s.name, "standing": standing[s.pk]}
                       for s in stages]}


class IntegrationApplicationCountsView(SignedReadView):
    required_scopes = (APPLICATION_READ,)

    @extend_schema(tags=["Server events"], auth=[{"ServerHMAC": []}], parameters=PAGE_PARAMETERS,
                   summary="Read application counts per event (server HMAC; applications:read)",
                   responses={200: ApplicationCountsPageSerializer, **ERRORS})
    def get(self, request):
        tenant = request.api_client.makerspace
        if (not is_servable(tenant) or not module_enabled(tenant, "events")
                or not feature_enabled(tenant, "events.api_read") or not admission_enabled(tenant)):
            raise NotFound()
        events = Event.objects.filter(makerspace=tenant, hackathon_applications__isnull=False).distinct()
        rows, cursor = keyset_page(request, events, subject="application_counts")
        return Response({"next_cursor": cursor, "results": [counts(event) for event in rows]})
