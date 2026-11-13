"""PIN-station badge routes (parity E-B2): a station prints the saved badge and reports it.

Same station cookie and origin check as the roster and sync routes. The station never edits a design, never
rotates a credential, and only serves confirmed registrants of the event it is bound to.
"""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from . import badge_desk, badge_prints
from .models import EventRegistration
from .serializers_badge_prints import BadgeReceiptBatchSerializer, BadgeReceiptResultSerializer, StationBadgeSerializer
from .views_checkin_station import GENERIC_ERROR, _StationCookieView

TAGS = ["Event check-in stations"]


class EventStationBadgeView(_StationCookieView):
    @extend_schema(
        tags=TAGS, summary="The saved badge design and one registrant's badge row for the PIN station",
        description="A print start: counts against `event_badge_prints_monthly` and answers 409 once it is used up.",
        request=None, responses={200: StationBadgeSerializer, 403: GENERIC_ERROR, 404: GENERIC_ERROR, 409: GENERIC_ERROR})
    def get(self, request, public_token, registration_id, *args, **kwargs):
        event, _credential, _session = self.station_session(request, public_token)
        badge_prints.require_desk_print(event)
        registration = get_object_or_404(EventRegistration.objects.select_related("event__makerspace"),
                                         pk=registration_id, event=event,
                                         status__in=("registered", "attended"))
        if registration.event_id != event.pk:
            raise NotFound()
        badge_prints.check_print_start(event)
        response = Response(badge_desk.desk_payload(event, registration=registration))
        response["Cache-Control"] = "private, no-store"
        return response


class EventStationBadgeReceiptsView(_StationCookieView):
    @extend_schema(
        tags=TAGS, summary="Report badges printed at the PIN station (idempotent by operation_id)",
        request=BadgeReceiptBatchSerializer,
        responses={200: BadgeReceiptResultSerializer, 400: GENERIC_ERROR, 403: GENERIC_ERROR, 404: GENERIC_ERROR})
    def post(self, request, public_token, *args, **kwargs):
        event, _credential, _session = self.station_session(request, public_token)
        badge_prints.require_desk_print(event)
        data = BadgeReceiptBatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        recorded, duplicates = badge_prints.record_receipts(event, data.validated_data["receipts"], actor=None,
                                                            method="station")
        return Response({"recorded": recorded, "duplicates": duplicates})
