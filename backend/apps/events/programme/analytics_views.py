"""Per-event analytics extras (G8) under live `manage_registrations` authority."""

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.event_permissions import MANAGE_REGISTRATIONS
from apps.events.views_invites import ERRORS

from .analytics_extras import extras
from .analytics_serializers import EventAnalyticsExtrasSerializer


class EventAnalyticsExtrasView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], responses={200: EventAnalyticsExtrasSerializer, **ERRORS},
        description="Arrivals by adaptive window (15 minutes to 8 hours), sign-ups per day, written-answer counts, check-in method split, feedback choice counts "
                    "(free text is never charted), waitlist conversion, series turnout and short-link "
                    "visits (null while events.short_links is off). Counts only, no people.")
    def get(self, request, pk):
        event = event_authority.get_event(request.user, pk, MANAGE_REGISTRATIONS)
        response = Response(EventAnalyticsExtrasSerializer(extras(event)).data)
        response["Cache-Control"] = "private, no-store"
        return response
