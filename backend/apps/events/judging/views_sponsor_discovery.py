"""Discover only sponsor scopes that the current source-aware authority admits."""
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from apps.events.contributions.models_roles import EventSponsor
from .api_common import PrivateView, admin_event, paginated, ERRORS
from .sponsors import track_scope


class AssignedSponsorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()


class AssignedSponsorPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AssignedSponsorSerializer(many=True)


class AssignedSponsorListView(PrivateView):
    @extend_schema(tags=["Event programme sponsors"], responses={200: AssignedSponsorPageSerializer, **ERRORS})
    def get(self, request, pk):
        event = admin_event(request, pk, "view_sponsor_track")
        rows = []
        # Filter IDs first; labels from unrelated sponsor relationships never cross.
        for row in EventSponsor.objects.filter(event=event, active=True).order_by("pk"):
            try:
                if track_scope(request.user, event, row.pk):
                    rows.append({"id": row.pk, "label": row.label})
            except Http404:
                continue
        return paginated(request, rows, AssignedSponsorSerializer)
