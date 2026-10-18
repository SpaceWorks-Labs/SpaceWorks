from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from apps.events.contributions.api_common import ProgrammeView, paginated, page_schema
from apps.events.contributions.models_shifts import EventShift
from apps.events.contributions.projections import shift
from apps.events.contributions.serializers import ShiftSerializer, CommandSerializer, ERRORS
from apps.events.contributions.ports import ports
from .models_queue import OfficeHoursBooking
from .office_hours_workflow import book, cancel
from .projections import booking
from .serializers import BookingSerializer, BookingInputSerializer


class OfficeHoursListView(ProgrammeView):
    @extend_schema(responses={200: page_schema("OfficeHoursSlotPage", ShiftSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        own = ports().teams.own_ids(actor_id=request.user.pk, event_id=pk)
        for team_id in own:
            ports().teams.require_eligible(event_id=pk, team_id=team_id, at=timezone.now())
        if not own:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        rows = EventShift.objects.filter(event_id=pk, kind="office_hours", state="open").order_by("starts_at", "pk")
        return paginated(request, rows, shift)


class OfficeHoursBookingListView(ProgrammeView):
    @extend_schema(responses={200: page_schema("OfficeHoursBookingPage", BookingSerializer), **ERRORS})
    def get(self, request, pk, makerspace_id):
        self.event(request, pk, makerspace_id)
        own = ports().teams.own_ids(actor_id=request.user.pk, event_id=pk)
        return paginated(request, OfficeHoursBooking.objects.filter(event_id=pk,
            team_id__in=own).order_by("pk"), booking)


class OfficeHoursBookingCreateView(ProgrammeView):
    @extend_schema(request=BookingInputSerializer, responses={201: BookingSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, slot_id):
        self.event(request, pk, makerspace_id)
        result = book(actor=request.user, event_id=pk, slot_id=slot_id,
                      payload=self.input(request, BookingInputSerializer))
        return Response(booking(result.row), status=result.status)


class OfficeHoursBookingCancelView(ProgrammeView):
    @extend_schema(request=CommandSerializer, responses={200: BookingSerializer, **ERRORS})
    def post(self, request, pk, makerspace_id, booking_id):
        self.event(request, pk, makerspace_id)
        result = cancel(actor=request.user, event_id=pk, booking_id=booking_id,
                        payload=self.input(request, CommandSerializer))
        return Response(booking(result.row))
