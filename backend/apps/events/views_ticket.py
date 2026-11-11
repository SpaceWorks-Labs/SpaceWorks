from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from zoneinfo import ZoneInfo
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.audit.services import record
from apps.events.checkin_roster import host_waiver_state
from apps.events.member_history import registrations_for_space
from apps.events.models import EventRegistration
from apps.events.participant_access import participant_space
from apps.events.credentials.serializers_ticket import ProgrammeTicketSerializer as MemberEventTicketSerializer
from apps.events.views_checkin import CHECKABLE_EVENT_STATUSES
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.makerspaces.confirmation_render import render_confirmation_png
from apps.makerspaces.guards import require_module


class TicketRenderThrottle(UserRateThrottle):
    scope = "event_ticket_render"
    rate = "20/hour"


def _owned_registration(user, makerspace_id, pk):
    space = participant_space(user, makerspace_id, pk)
    require_module(space, "events")
    return get_object_or_404(
        registrations_for_space(space, user).select_related("event"), member=user, pk=pk,
    )


def _png_available(registration):
    if registration.credential_mode == "inert":
        return False
    if registration.credential_mode == "v2":
        from .credentials.workflow import current
        if current(registration) is None:
            return False
    if (registration.status not in (EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED)
            or registration.event.status not in CHECKABLE_EVENT_STATUSES):
        return False
    needs_waiver_evidence = (
        registration.registration_audience == "participating_organizations"
        or (
            registration.registered_via_makerspace_id
            and registration.registered_via_makerspace_id != registration.event.makerspace_id
        )
    )
    if needs_waiver_evidence:
        return host_waiver_state(registration) != "missing"
    return True


ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404, 429)}


class MemberEventTicketView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TicketRenderThrottle]

    @extend_schema(tags=["Member activity"], summary="Read the caller's event ticket",
                   responses={200: MemberEventTicketSerializer, **ERRORS})
    def get(self, request, makerspace_id, pk):
        registration = _owned_registration(request.user, makerspace_id, pk)
        data = MemberEventTicketSerializer({
            "registration_id": registration.pk, "status": registration.status,
            "event": registration.event, "ticket_png_available": _png_available(registration),
        }).data
        attendance = registration.check_in_events.order_by("-recorded_at", "-pk").first() if registration.status == "attended" else None
        data["attended_at"] = attendance.attended_at.isoformat() if attendance else None
        data["credential_mode"] = registration.credential_mode
        from .online_delivery import join_url_for, map_url, public_mode
        data["delivery_mode"] = public_mode(registration.event)
        data["join_url"] = join_url_for(registration)
        data["map_url"] = map_url(registration.event)
        data["pay_by"] = registration.pay_by.isoformat() if registration.pay_by else None
        response = Response(data)
        response["Cache-Control"] = "private, no-store"
        return response


class MemberEventTicketPngView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TicketRenderThrottle]

    @extend_schema(tags=["Member activity"], summary="Download the caller's registered or attended ticket",
                   responses={(200, "image/png"): OpenApiResponse(OpenApiTypes.BINARY), **ERRORS})
    def get(self, request, makerspace_id, pk):
        registration = _owned_registration(request.user, makerspace_id, pk)
        if not _png_available(registration):
            from rest_framework.exceptions import NotFound
            raise NotFound()
        event = registration.event
        when = timezone.localtime(event.starts_at, ZoneInfo(event.timezone_name)).strftime("%d %b %Y %H:%M %Z")
        if registration.credential_mode == "v2":
            from .credentials.workflow import owner_payload
            payload = owner_payload(registration, actor=request.user)
        else:
            payload = str(registration.checkin_token)
        png = render_confirmation_png(qr_value=payload, title=event.title,
                                      lines=(registration.name, when, event.location, registration.status))
        record(request.user, "event.ticket_downloaded", makerspace=event.makerspace, target=registration)
        response = HttpResponse(png, content_type="image/png")
        response["Cache-Control"] = "private, no-store"
        response["Content-Disposition"] = f'attachment; filename="event-ticket-{registration.pk}.png"'
        return response
