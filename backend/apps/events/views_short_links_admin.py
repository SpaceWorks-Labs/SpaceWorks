"""Staff routes for an event's short link: read with visit counts, create, regenerate.

Authority is the event's `publish_schedule` (the publishing authority, promised-items
SPEC §7 Q1); collaborators hold it only when granted. While `events.short_links` is off
every route answers 404 and the stored codes are kept.
"""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.folded_capabilities import require_capability
from apps.makerspaces.public_page_access import canonical_origin

from . import event_authority, short_links
from .event_permissions import PUBLISH_SCHEDULE

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 423, 503)}


class VisitDaySerializer(serializers.Serializer):
    day = serializers.DateField()
    count = serializers.IntegerField(min_value=0)


class ShortLinkSerializer(serializers.Serializer):
    code = serializers.CharField(allow_null=True)
    url = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)
    visits_30d = VisitDaySerializer(many=True)
    total_visits = serializers.IntegerField(min_value=0)


class RegenerateInput(serializers.Serializer):
    confirm = serializers.BooleanField()

    def validate_confirm(self, value):
        if value is not True:
            raise serializers.ValidationError("Confirm that the old link stops working.")
        return value


def short_link_payload(event, link):
    return {"code": link.code if link else None,
            "url": f"{canonical_origin(event.makerspace)}/e/{link.code}" if link else None,
            "created_at": link.created_at if link else None,
            "visits_30d": short_links.visits(event, days=30), "total_visits": short_links.total_visits(event)}


def private(data, status=200):
    return Response(data, status=status, headers={"Cache-Control": "private, no-store"})


def _event(request, pk):
    event = event_authority.get_event(request.user, pk, PUBLISH_SCHEDULE)
    require_capability(event.makerspace, short_links.FEATURE)
    return event


class EventShortLinkView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Read the event's short link and its visit counts",
                   description="404 while `events.short_links` is off.",
                   request=None, responses={200: ShortLinkSerializer, **ERRORS})
    def get(self, request, pk):
        event = _event(request, pk)
        return private(ShortLinkSerializer(short_link_payload(event, short_links.live_link(event))).data)

    @extend_schema(tags=["Admin events"], summary="Create the event's short link (idempotent)",
                   description="Returns the live code when one already exists. Published events only. "
                               "Audited as `event.short_link.created`.",
                   request=None, responses={200: ShortLinkSerializer, 201: ShortLinkSerializer, **ERRORS})
    def post(self, request, pk):
        event = _event(request, pk)
        link, created = short_links.create(event, actor=request.user)
        return private(ShortLinkSerializer(short_link_payload(event, link)).data, 201 if created else 200)


class EventShortLinkRegenerateView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], summary="Retire the short link and issue a new one",
                   description="The old code returns 404 at once and is never issued again. "
                               "Audited as `event.short_link.regenerated`.",
                   request=RegenerateInput, responses={200: ShortLinkSerializer, **ERRORS})
    def post(self, request, pk):
        event = _event(request, pk)
        RegenerateInput(data=request.data).is_valid(raise_exception=True)
        link = short_links.regenerate(event, actor=request.user)
        return private(ShortLinkSerializer(short_link_payload(event, link)).data)
