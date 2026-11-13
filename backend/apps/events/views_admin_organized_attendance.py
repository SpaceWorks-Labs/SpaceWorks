"""Organizer-scoped attendance across partner venues (open item A25, role-completeness EB14).

An organization's organizers see how many people registered for and attended every event the
organization ran, wherever it ran. Authority is exactly the organizer-discovery predicate of
`OrganizedEventListView` (`event_authority.organized_events_for`): per-event organizer authority,
no venue authority, and nothing about a venue is read beyond its name. Only counts leave this
route -- no attendee, contact or payment data -- so partner venues stay opaque.
"""

from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.events import event_authority
from apps.events.models import Event, EventRegistration
from apps.hardware_requests.exceptions import ErrorSerializer

ERRORS = {401: ErrorSerializer, 403: ErrorSerializer, 404: ErrorSerializer}
LIMIT = 500


class OrganizedAttendanceRowSerializer(serializers.Serializer):
    event_id = serializers.IntegerField()
    title = serializers.CharField()
    venue_name = serializers.CharField()
    starts_at = serializers.DateTimeField()
    status = serializers.CharField()
    registered = serializers.IntegerField()
    attended = serializers.IntegerField()
    attendance_rate_percent = serializers.FloatField(allow_null=True)


class OrganizedAttendanceSerializer(serializers.Serializer):
    results = OrganizedAttendanceRowSerializer(many=True)
    totals = serializers.DictField(child=serializers.IntegerField())
    truncated = serializers.BooleanField()


def _rate(attended, registered):
    return round(100.0 * attended / registered, 1) if registered else None


class OrganizedEventAttendanceView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(
        tags=["Events"],
        summary="Attendance of the events the actor's organizations organize, across venues",
        description=("Counts only. Registered = registered plus attended; the rate divides attended by "
                     "registered. Same organizer authority as the organized-events list."),
        request=None, responses={200: OrganizedAttendanceSerializer, **ERRORS},
    )
    def get(self, request, *args, **kwargs):
        rows = event_authority.organized_events_for(request.user, Event.objects.all()).select_related("makerspace")
        rows = rows.annotate(
            attended_count=Count("registrations", filter=Q(registrations__status=EventRegistration.Status.ATTENDED)),
            registered_count=Count("registrations", filter=Q(registrations__status__in=(
                EventRegistration.Status.REGISTERED, EventRegistration.Status.ATTENDED))),
        ).order_by("-starts_at", "-id")
        page = list(rows[:LIMIT + 1])
        truncated = len(page) > LIMIT
        results = [{
            "event_id": event.pk, "title": event.title, "venue_name": event.makerspace.name,
            "starts_at": event.starts_at, "status": event.status, "registered": event.registered_count,
            "attended": event.attended_count,
            "attendance_rate_percent": _rate(event.attended_count, event.registered_count),
        } for event in page[:LIMIT]]
        totals = {"events": len(results), "registered": sum(row["registered"] for row in results),
                  "attended": sum(row["attended"] for row in results)}
        return Response(OrganizedAttendanceSerializer(
            {"results": results, "totals": totals, "truncated": truncated}).data)
