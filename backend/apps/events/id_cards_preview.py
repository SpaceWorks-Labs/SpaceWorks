"""Batch print preview for an event's active ID cards (the first sheet, before a job)."""
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.card_designs import sheet_preview
from apps.card_designs.serializers_history import SheetPreviewRequestSerializer, SheetPreviewSerializer
from apps.card_designs.views_jobs import job_params
from apps.card_designs.views_sheet_preview import DESCRIPTION
from apps.openapi_errors import errors

from .id_cards_views import organiser_event
from .models import EventIdCard

TAGS = ["Event ID cards"]


def event_card_ids(event, values):
    """The active cards a bulk job or its preview prints, narrowed by ids, roles and check-in."""
    rows = EventIdCard.objects.filter(event=event, status="active")
    if values.get("card_ids"):
        rows = rows.filter(pk__in=values["card_ids"])
    if values.get("roles"):
        rows = rows.filter(role__in=values["roles"])
    if values.get("checked_in") is not None:
        attended = rows.filter(registration__status="attended")
        rows = attended if values["checked_in"] else rows.exclude(pk__in=attended.values("pk"))
    return list(rows.order_by("pk").values_list("pk", flat=True))


class EventCardSheetPreviewView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "card_render"

    @extend_schema(tags=TAGS, summary="Preview the first print sheet of an event card bulk job",
                   description=DESCRIPTION, request=SheetPreviewRequestSerializer,
                   responses={200: SheetPreviewSerializer, **errors(400, 401, 403, 404, 429)})
    def post(self, request, pk):
        event = organiser_event(request.user, pk)
        data = SheetPreviewRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        values = data.validated_data
        return Response(sheet_preview.preview(request.user, event.makerspace, "event_card", event_card_ids(event, values),
                                              job_params(values),
                                              scope="event"))
