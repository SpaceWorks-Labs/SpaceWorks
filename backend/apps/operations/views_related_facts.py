"""Staff GET routes for the event/booking related-facts views (decision 216 item 13)."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from .related_facts import booking_facts, event_facts

SOURCE_HELP = "The one model this section reads; sections are never derived from each other."


class RelatedFactsSubject(serializers.Serializer):
    kind = serializers.CharField(help_text="event | booking")
    id = serializers.IntegerField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    machine_id = serializers.IntegerField(allow_null=True, required=False)


class RelatedFactsRegistrations(serializers.Serializer):
    source = serializers.CharField(help_text=SOURCE_HELP)
    by_status = serializers.DictField(child=serializers.IntegerField())


class RelatedFactsAttendance(serializers.Serializer):
    source = serializers.CharField(help_text=SOURCE_HELP)
    attended_registrations = serializers.IntegerField()
    check_in_records = serializers.IntegerField()
    registrations_with_check_in = serializers.IntegerField()
    check_in_records_by_source = serializers.DictField(child=serializers.IntegerField())


class RelatedFactsPresence(serializers.Serializer):
    source = serializers.CharField(help_text=SOURCE_HELP)
    window_start = serializers.DateTimeField()
    window_end = serializers.DateTimeField()
    sessions_overlapping = serializers.IntegerField()
    distinct_people = serializers.IntegerField()
    sessions_linked_to_event = serializers.IntegerField(required=False)
    subject_person_presence = serializers.CharField(
        required=False, help_text="recorded | not_recorded | withheld: the booker's own presence, "
                                  "withheld when presence display privacy hides them.")


class RelatedFactsArrival(serializers.Serializer):
    source = serializers.CharField(help_text=SOURCE_HELP)
    booking_status = serializers.CharField()
    arrived_at = serializers.DateTimeField(allow_null=True)
    departed_at = serializers.DateTimeField(allow_null=True)
    arrival_confirmations = serializers.IntegerField()
    arrival_reversals = serializers.IntegerField()


class RelatedFactsMachineSession(serializers.Serializer):
    session_id = serializers.IntegerField()
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True)
    source = serializers.CharField()
    minutes = serializers.IntegerField()
    by_subject_person = serializers.BooleanField()


class RelatedFactsMachineSessions(serializers.Serializer):
    source = serializers.CharField(help_text=SOURCE_HELP)
    machine_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    window_start = serializers.DateTimeField()
    window_end = serializers.DateTimeField()
    sessions_overlapping = serializers.IntegerField()
    sessions = RelatedFactsMachineSession(many=True)


class EventRelatedFactsSerializer(serializers.Serializer):
    subject = RelatedFactsSubject()
    registrations = RelatedFactsRegistrations(required=False)
    attendance = RelatedFactsAttendance(required=False)
    presence = RelatedFactsPresence(required=False)


class BookingRelatedFactsSerializer(serializers.Serializer):
    subject = RelatedFactsSubject()
    arrival = RelatedFactsArrival(required=False)
    presence = RelatedFactsPresence(required=False)
    machine_sessions = RelatedFactsMachineSessions(required=False)


ERRORS = {
    401: OpenApiResponse(description="Authentication required."),
    403: OpenApiResponse(description="No view authority over this event or booking."),
    404: OpenApiResponse(description="Unknown subject in this makerspace, or no section is available."),
}
NOTE = ("Read-only. Each section is present only when its own module is on and the actor holds that "
        "source's authority; opted-out people appear only inside counts.")


class EventRelatedFactsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin events"], description="Registration, attendance and presence for one event. " + NOTE,
                   responses={200: EventRelatedFactsSerializer, **ERRORS})
    def get(self, request, makerspace_id, event_id):
        data = event_facts(request.user, makerspace_id, event_id)
        return Response(EventRelatedFactsSerializer(data).data)


class BookingRelatedFactsView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin bookings"],
                   description="Arrival, presence and booked-machine sessions for one booking. " + NOTE,
                   responses={200: BookingRelatedFactsSerializer, **ERRORS})
    def get(self, request, makerspace_id, booking_id):
        data = booking_facts(request.user, makerspace_id, booking_id)
        return Response(BookingRelatedFactsSerializer(data).data)
