"""Decision 242(l): superadmin cross-space queues, per-space snapshot, unread inbox and platform search.

Superadmin only (a browser session; a native grant is refused by the platform context), counts only, never
exposed to any other role. The inbox and the search are audited (no search text is stored) and throttled.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.servability import servable_queryset
from apps.operations import platform_cross_space as cross
from apps.operations.platform_scope import _platform_context_for_view

ERRORS = {code: OpenApiResponse(ErrorSerializer) for code in (401, 403, 404, 429)}
NO_STORE = {"Cache-Control": "private, no-store"}
COUNTS = serializers.DictField(child=serializers.IntegerField(), help_text=f"Keys: {', '.join(cross.METRICS)}.")


class PlatformQueueThrottle(UserRateThrottle):
    scope = "platform_queues"
    rate = "30/min"


class PlatformSearchThrottle(UserRateThrottle):
    scope = "platform_search"
    rate = "20/min"


class QueueRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    counts = COUNTS
    total = serializers.IntegerField()


class QueuesSerializer(serializers.Serializer):
    spaces = QueueRowSerializer(many=True)


class SnapshotSerializer(serializers.Serializer):
    class Meta:
        ref_name = "PlatformCrossSpaceSnapshot"

    id = serializers.IntegerField()
    name = serializers.CharField()
    slug = serializers.CharField()
    hosted = serializers.BooleanField(help_text="Usage is shown either way; limits are null for an Own space.")
    counts = COUNTS
    usage = serializers.DictField(child=serializers.JSONField())


class InboxRowSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    personal_unread = serializers.IntegerField(help_text="The caller's own unread inbox rows in that space.")
    notices_unread = serializers.IntegerField(help_text="Unread space-wide notices in that space.")


class InboxSerializer(serializers.Serializer):
    class Meta:
        ref_name = "PlatformCrossSpaceInbox"

    spaces = InboxRowSerializer(many=True)
    total = serializers.IntegerField()


class SearchHitSerializer(serializers.Serializer):
    class Meta:
        ref_name = "PlatformCrossSpaceSearchHit"

    kind = serializers.ChoiceField(choices=["space", "person", "receipt"])
    space_id = serializers.IntegerField(required=False)
    account_id = serializers.IntegerField(required=False)
    space_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    label = serializers.CharField()


class SearchSerializer(serializers.Serializer):
    results = SearchHitSerializer(many=True)


class _PlatformView(APIView):
    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "head", "options"]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _platform_context_for_view(request)  # refuses a native session; superadmin browser session only


class PlatformQueuesView(_PlatformView):
    throttle_classes = [PlatformQueueThrottle]

    @extend_schema(tags=["Platform"], summary="Queues and safety by space (counts only)",
                   responses={200: QueuesSerializer, **ERRORS})
    def get(self, request):
        return Response({"spaces": cross.queues_by_space()}, headers=NO_STORE)


class PlatformSnapshotView(_PlatformView):
    throttle_classes = [PlatformQueueThrottle]

    @extend_schema(tags=["Platform"], summary="One space's queue counts and usage (read-only snapshot)",
                   responses={200: SnapshotSerializer, **ERRORS})
    def get(self, request, makerspace_id):
        space = get_object_or_404(servable_queryset(), pk=makerspace_id)
        return Response(cross.space_snapshot(space), headers=NO_STORE)


class PlatformInboxView(_PlatformView):
    throttle_classes = [PlatformQueueThrottle]

    @extend_schema(tags=["Platform"], summary="Unread inbox counts across spaces (superadmin only, audited)",
                   responses={200: InboxSerializer, **ERRORS})
    def get(self, request):
        rows = cross.unread_by_space(request.user)
        audit.record(request.user, "platform.inbox_viewed", target_type="platform_inbox", meta={"spaces": len(rows)})
        return Response({"spaces": rows, "total": sum(r["personal_unread"] + r["notices_unread"] for r in rows)},
                        headers=NO_STORE)


class PlatformSearchView(_PlatformView):
    throttle_classes = [PlatformSearchThrottle]

    @extend_schema(tags=["Platform"], summary="Platform search: spaces, people by account, receipt numbers",
                   description="Superadmin only, audited (the search text is never stored) and throttled. Hits name a "
                               "space and a kind; no row from inside a space is returned.",
                   parameters=[OpenApiParameter("q", str, required=True, description="At least 3 characters.")],
                   responses={200: SearchSerializer, 400: OpenApiResponse(ErrorSerializer), **ERRORS})
    def get(self, request):
        term = (request.query_params.get("q") or "").strip()
        if len(term) < 3 or len(term) > 100:
            raise serializers.ValidationError({"q": "Use 3 to 100 characters."})
        hits = cross.platform_search(term)
        audit.record(request.user, "platform.searched", target_type="platform_search",
                     meta={"hits": len(hits), "kinds": sorted({hit["kind"] for hit in hits})})
        return Response({"results": hits}, headers=NO_STORE)
