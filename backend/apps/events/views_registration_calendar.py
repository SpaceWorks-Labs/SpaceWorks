"""One owned registration calendar; never opens member history to account-only users."""

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.audit.services import record
from apps.hardware_requests.exceptions import ErrorSerializer
from .models import EventRegistration
from .services_calendar import render_member_calendar
from .views_ticket import TicketRenderThrottle, _owned_registration


class MemberEventRegistrationCalendarView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TicketRenderThrottle]

    @extend_schema(
        tags=["Member events"], summary="Download one owned registration calendar",
        description="Exact row ownership and historical admission audience authorize this read; current organization eligibility is not required. No access to other member history.",
        responses={(200, "text/calendar"): OpenApiResponse(OpenApiTypes.BINARY),
                   **{code: ErrorSerializer for code in (400, 401, 403, 404, 429)}},
    )
    def get(self, request, makerspace_id, pk):
        row = _owned_registration(request.user, makerspace_id, pk)
        payload = render_member_calendar(row.event.makerspace, EventRegistration.objects.filter(pk=row.pk))
        record(request.user, "event.registration_calendar_downloaded", makerspace=row.event.makerspace, target=row)
        response = HttpResponse(payload, content_type="text/calendar; charset=utf-8")
        response["Cache-Control"] = "private, no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["Content-Disposition"] = f'attachment; filename="registration-{row.pk}.ics"'
        return response
