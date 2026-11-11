"""Online desk routes for badge printing (parity E-B2): the published badges, and the print receipts.

Both need the event's `CHECK_IN` grant and `events.badge_desk_print` (404 while it is off). The desk route is a
print START, so it is the point the `event_badge_prints_monthly` limit refuses (409); receipts are evidence of a
print that already happened and are never refused.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.openapi_errors import errors

from . import badge_desk, badge_prints
from .event_permissions import CHECK_IN
from .id_cards_views import organiser_event
from .models import EventRegistration
from .serializers_badge_prints import BadgeDeskSerializer, BadgeReceiptBatchSerializer, BadgeReceiptResultSerializer

TAGS = ["Event badges"]


def desk_event(actor, pk):
    event = organiser_event(actor, pk, CHECK_IN)
    badge_prints.require_desk_print(event)
    return event


class EventBadgeDeskView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAGS, summary="The published badge designs, logos and (optionally) badge rows for an online desk",
        description="Per role, the published design (compiled layers + badge settings) the desk renders locally, "
                    "the logos as small data URLs, and with `registration_id` that person's badge row or with "
                    "`status_set` up to 500 rows (`all` adds waitlisted and pending people as provisional badges). "
                    "A single-person request is a print start and counts against `event_badge_prints_monthly`.",
        parameters=[OpenApiParameter("registration_id", int), OpenApiParameter(
            "status_set", str, enum=list(badge_desk.STATUS_SETS))],
        request=None, responses={200: BadgeDeskSerializer, **errors(400, 401, 403, 404, 409)})
    def get(self, request, pk):
        event = desk_event(request.user, pk)
        registration, status_set = None, request.query_params.get("status_set") or None
        if status_set is not None and status_set not in badge_desk.STATUS_SETS:
            raise ValidationError({"status_set": "Unknown status set."})
        if request.query_params.get("registration_id"):
            try:
                registration_id = int(request.query_params["registration_id"])
            except ValueError:
                raise ValidationError({"registration_id": "Use a registration id."}) from None
            registration = get_object_or_404(EventRegistration.objects.select_related("event__makerspace"),
                                             pk=registration_id, event=event)
            badge_prints.check_print_start(event)
        response = Response(badge_desk.desk_payload(event, registration=registration, status_set=status_set))
        response["Cache-Control"] = "private, no-store"
        return response


class EventBadgeReceiptsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=TAGS, summary="Report badges printed at a desk (idempotent by operation_id, at most 200)",
        description="Append-only. Audited as `event_badge.printed` (count, method, stock, role; no names).",
        request=BadgeReceiptBatchSerializer, responses={200: BadgeReceiptResultSerializer, **errors(400, 401, 403, 404)})
    def post(self, request, pk):
        event = desk_event(request.user, pk)
        data = BadgeReceiptBatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        recorded, duplicates = badge_prints.record_receipts(event, data.validated_data["receipts"], actor=request.user)
        return Response({"recorded": recorded, "duplicates": duplicates})
