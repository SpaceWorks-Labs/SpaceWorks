"""Typed session-only interface for the existing-booking venue decision."""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.loan_context_access import safe_id
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from apps.makerspaces.models import Makerspace
from apps.makerspaces.servability import servable_queryset
from apps.makerspaces.loan_context_generations import validate_generations
from .booking_decision_access import authorized_booking, authorized_event
from .booking_decision_replacement import replaceable, reservation_chain
from .booking_decision_service import DecisionConflict, _fee_state, create_decision
from .models_booking_decision import EventBookingDecision
from .venue_conflicts import VenueConflictSerializer, event_room_conflicts
from django.utils.translation import gettext

MAX_SAFE = 9007199254740991


class DecisionInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not hasattr(data, "keys") or set(data.keys()) - set(self.fields):
            raise serializers.ValidationError(gettext("Unexpected decision fields."))
        return super().to_internal_value(data)

    operation_id = serializers.UUIDField()
    expected_generation = serializers.UUIDField(allow_null=True)
    expected_revision = serializers.IntegerField(min_value=0, max_value=MAX_SAFE)
    expected_events_epoch = serializers.UUIDField()
    expected_bookings_epoch = serializers.UUIDField()
    confirm_billing_owner = serializers.ChoiceField(choices=["booking"])
    existing_booking_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    allow_partial_coverage = serializers.BooleanField(
        required=False, default=False,
        help_text="Decision 223 G4: link a booking that does not cover the whole event window. Without it "
                  "the link is refused with 409 `booking_does_not_cover_event`. Audited.")


class Window(serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()


class HistoryEntry(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    status = serializers.CharField()


class DecisionOutput(serializers.Serializer):
    generation = serializers.UUIDField(allow_null=True)
    revision = serializers.IntegerField(min_value=0, max_value=MAX_SAFE)
    events_epoch = serializers.UUIDField()
    bookings_epoch = serializers.UUIDField()
    state = serializers.ChoiceField(choices=["absent", "linked", "booking_unavailable"])
    booking_id = serializers.IntegerField(allow_null=True, min_value=1, max_value=MAX_SAFE)
    billing_owner = serializers.ChoiceField(choices=["booking"], allow_null=True)
    event_window = Window(required=False)
    booking_window = Window(allow_null=True, required=False)
    reservation_state = serializers.ChoiceField(
        choices=["pending", "confirmed", "historical", "unavailable"], required=False,
    )
    sync = serializers.ChoiceField(choices=["matched", "different", "unavailable"], required=False)
    fee_state = serializers.ChoiceField(choices=["none", "free_no_debt", "configured", "historical_debt"], required=False)
    replayed = serializers.BooleanField(required=False)
    warnings = serializers.ListField(child=serializers.JSONField(), required=False, help_text=(
        "Decision 223: non-blocking warnings after linking, e.g. `event_capacity_above_room` "
        "(event capacity exceeds the room's), `venue_pending`, `venue_not_covered`."))
    current_booking_id = serializers.IntegerField(
        allow_null=True, required=False, min_value=1, max_value=MAX_SAFE,
        help_text="The event's current reservation: the linked booking or its latest replacement.")
    current_status = serializers.ChoiceField(choices=[
        "pending", "confirmed", "rejected", "cancelled", "completed", "no_show"], required=False)
    replaceable = serializers.BooleanField(
        required=False, help_text="The current reservation was rejected or cancelled and may be replaced.")
    history = HistoryEntry(many=True, required=False,
                           help_text="Earlier reservations, oldest first; each keeps its own debt and receipts.")
    event_status = serializers.ChoiceField(
        choices=["draft", "published", "cancelled", "completed"], required=False,
        help_text="A cancelled event never cancels its booking or debt; staff cancel the booking in Bookings.")
    coverage = serializers.ChoiceField(
        choices=["covers", "not_covered"], required=False,
        help_text="Whether the current reservation's window still contains the event's start and end. "
                  "Nothing is moved automatically; reschedule or replace through Bookings.")
    current_space_id = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_SAFE, help_text="The current reservation's room.")
    conflicts = VenueConflictSerializer(many=True, required=False, help_text=(
        "Room outages, machine repair and closures meeting the event's time in the current room. "
        "Flagged only: the booking, the event and their charges are never changed automatically."))


def _maker(pk):
    return get_object_or_404(servable_queryset(Makerspace.objects.all()), pk=safe_id(pk))


def _epochs(maker):
    validate_generations(maker.loan_context_generations)
    return {"events_epoch": maker.loan_context_generations["events"],
            "bookings_epoch": maker.loan_context_generations["bookings"]}


def _response(row, maker, *, replayed):
    return {"generation": row.generation, "revision": row.revision, **_epochs(maker),
            "state": "linked", "booking_id": row.booking_id,
            "billing_owner": "booking", "replayed": replayed}


def _reservation_state(booking):
    status = booking.Status
    if booking.status in (status.COMPLETED, status.NO_SHOW):
        return "historical"
    if booking.ends_at <= timezone.now():
        return "historical" if booking.status == status.CONFIRMED else "unavailable"
    if booking.space.is_active and booking.status in (status.PENDING, status.CONFIRMED):
        return booking.status
    return "unavailable"


def _coverage(event, booking):
    covered = booking.starts_at <= event.starts_at and event.ends_at <= booking.ends_at
    return "covers" if covered else "not_covered"


class EventBookingDecisionView(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request, "api_client", None) or getattr(request, "person_credential", None):
            raise PermissionDenied(gettext("This endpoint requires a staff session."))

    @extend_schema(request=None, auth=[{"jwtAuth": []}], responses={200: DecisionOutput, **PUBLIC_ERROR_RESPONSES, 423: OpenApiResponse(ErrorSerializer, description="Tenant write fence is closed.")})
    def get(self, request, makerspace_id, event_id):
        maker = _maker(makerspace_id)
        event = authorized_event(request.user, maker, event_id)
        row = EventBookingDecision.objects.filter(makerspace_id=maker.pk, event_id=event.pk).first()
        chain = reservation_chain(request.user, maker, row, authorize=authorized_booking) if row else []
        booking = chain[-1] if chain else None
        fee_state = _fee_state(maker, event, lock=False)
        if fee_state == "unresolved":
            raise DecisionConflict("venue_debt_history_requires_review")
        base = {**_epochs(maker), "generation": row.generation if row else None,
                "revision": row.revision if row else 0,
                "billing_owner": "booking" if row else None,
                "event_window": {"starts_at": event.starts_at, "ends_at": event.ends_at},
                "event_status": event.status, "fee_state": fee_state}
        if row is None or row.booking_id is None:
            return Response({**base, "state": "booking_unavailable" if row else "absent",
                             "booking_id": None, "booking_window": None, "sync": "unavailable"})
        return Response({**base, "state": "linked", "booking_id": row.booking_id,
                         "current_booking_id": booking.pk, "current_status": booking.status,
                         "current_space_id": booking.space_id, "coverage": _coverage(event, booking),
                         "conflicts": event_room_conflicts(request.user, event, booking),
                         "replaceable": replaceable(event, booking),
                         "history": [{"booking_id": old.pk, "status": old.status} for old in chain[:-1]],
                         "reservation_state": _reservation_state(booking),
                         "booking_window": {"starts_at": booking.starts_at, "ends_at": booking.ends_at},
                         "sync": "matched" if (event.starts_at, event.ends_at) == (booking.starts_at, booking.ends_at) else "different"})

    @extend_schema(request=DecisionInput, auth=[{"jwtAuth": []}], responses={200: DecisionOutput, 201: DecisionOutput, **PUBLIC_ERROR_RESPONSES, 423: OpenApiResponse(ErrorSerializer, description="Tenant write fence is closed.")})
    def post(self, request, makerspace_id, event_id):
        body = DecisionInput(data=request.data)
        body.is_valid(raise_exception=True)
        maker = _maker(makerspace_id)
        data = body.validated_data
        row, replayed = create_decision(request.user, maker, event_id,
            booking_id=data["existing_booking_id"], operation_id=data["operation_id"],
            expected_generation=data["expected_generation"], expected_revision=data["expected_revision"],
            expected_events_epoch=data["expected_events_epoch"], expected_bookings_epoch=data["expected_bookings_epoch"],
            allow_partial_coverage=data["allow_partial_coverage"])
        maker.refresh_from_db(fields=["loan_context_generations"])
        from .venue_publish_check import publish_check
        payload = {**_response(row, maker, replayed=replayed), "warnings": publish_check(row.event)["warnings"]}
        return Response(payload, status=200 if replayed else 201)
