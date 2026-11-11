"""Session-only staff routes for an event's workshop machine bookings (P2-1)."""
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from .machine_booking_link_rows import link_row, link_rows
from .machine_booking_links import MAX_LINKS, link_machine_booking, replace_machine_link, unlink_machine_booking
from .machine_link_access import authorized_workshop_event
from .venue_conflicts import VenueConflictSerializer
from .views_booking_decision import MAX_SAFE, Window, _maker
from .views_booking_decision_replacement import ReplacementInput, ReplacementOutput

STATUSES = ["pending", "confirmed", "rejected", "cancelled", "completed", "no_show"]
FENCE = {423: OpenApiResponse(ErrorSerializer, description="Tenant write fence is closed.")}


class WorkshopMachineLinkInput(serializers.Serializer):
    def to_internal_value(self, data):
        if not hasattr(data, "keys") or set(data.keys()) - set(self.fields):
            raise serializers.ValidationError(gettext("Unexpected fields."))
        return super().to_internal_value(data)

    booking_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE,
                                          help_text="An existing pending or confirmed booking of one machine's time.")
    certification_override_reason = serializers.CharField(
        max_length=1000, allow_blank=True, required=False,
        help_text="Honoured only for staff with authority over the machine type; every override is audited.")


class MachineReplacementInput(ReplacementInput):
    certification_override_reason = serializers.CharField(
        max_length=1000, allow_blank=True, required=False,
        help_text="Honoured only for staff with authority over the machine type; audited. Covers the booker and every organizer.")


class WorkshopMachineWarning(serializers.Serializer):
    code = serializers.ChoiceField(choices=["room_outage", "machine_repair", "machine_lockout", "certification"])
    state = serializers.ChoiceField(choices=["blocked", "warning"])
    detail = serializers.CharField()


class WorkshopMachineHistory(serializers.Serializer):
    booking_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    status = serializers.ChoiceField(choices=STATUSES)


class WorkshopMachineLink(serializers.Serializer):
    link_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    state = serializers.ChoiceField(choices=["linked", "booking_unavailable"])
    booking_id = serializers.IntegerField(allow_null=True, min_value=1, max_value=MAX_SAFE,
                                          help_text="The originally linked booking; never rewritten.")
    current_booking_id = serializers.IntegerField(required=False, min_value=1, max_value=MAX_SAFE,
                                                  help_text="The linked booking or its latest replacement.")
    current_status = serializers.ChoiceField(choices=STATUSES, required=False)
    current_space_id = serializers.IntegerField(required=False, min_value=1, max_value=MAX_SAFE)
    space_name = serializers.CharField(required=False)
    machine_id = serializers.IntegerField(required=False, allow_null=True)
    machine_name = serializers.CharField(required=False, allow_blank=True)
    machine_type_id = serializers.IntegerField(required=False, allow_null=True)
    booking_window = Window(required=False)
    reservation_state = serializers.ChoiceField(choices=["pending", "confirmed", "historical", "unavailable"],
                                                required=False)
    replaceable = serializers.BooleanField(required=False)
    history = WorkshopMachineHistory(many=True, required=False)
    warnings = WorkshopMachineWarning(many=True, required=False,
                       help_text="Advisory admission facts; a lockout never refuses the booking.")
    conflicts = VenueConflictSerializer(many=True, required=False, help_text=(
        "Machine repair, room outages and closures meeting the booking's time. Flagged only; the "
        "booking and its charge are never changed automatically."))
    replayed = serializers.BooleanField(required=False)


class WorkshopMachineList(serializers.Serializer):
    event_window = Window()
    event_status = serializers.ChoiceField(choices=["draft", "published", "cancelled", "completed"])
    results = WorkshopMachineLink(many=True)
    withheld = serializers.IntegerField(min_value=0, help_text="Links whose booking or machine you cannot manage.")
    max_links = serializers.IntegerField()


class _SessionOnly(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request, "api_client", None) or getattr(request, "person_credential", None):
            raise PermissionDenied(gettext("This endpoint requires a staff session."))


class EventWorkshopMachinesView(_SessionOnly):
    @extend_schema(request=None, auth=[{"jwtAuth": []}], summary="List the event's workshop machine bookings",
                   description="Needs the events, bookings and machines modules, tenant-wide manage_events and "
                               "manage_bookings, event visibility, and manage_reservations plus machine authority "
                               "(per-type reach) on each booking; other links are only counted.",
                   responses={200: WorkshopMachineList, **PUBLIC_ERROR_RESPONSES})
    def get(self, request, makerspace_id, event_id):
        maker = _maker(makerspace_id)
        event = authorized_workshop_event(request.user, maker, event_id)
        rows, withheld = link_rows(request.user, maker, event)
        return Response({"event_window": {"starts_at": event.starts_at, "ends_at": event.ends_at},
                         "event_status": event.status, "results": rows, "withheld": withheld,
                         "max_links": MAX_LINKS})

    @extend_schema(request=WorkshopMachineLinkInput, auth=[{"jwtAuth": []}], summary="Link a machine booking to the event",
                   description="The booking keeps its own Booking-owned machine-time charge; no event venue fee "
                               "or room charge is involved. Re-checks the booker's certification (403 "
                               "`certification_required`) and the repair gate (409 `machine_under_repair`). "
                               "409 codes: `booking_already_linked`, `not_linkable`, `too_many_machines`, "
                               "`booker_required`. Linking the same booking again answers 200.",
                   responses={200: WorkshopMachineLink, 201: WorkshopMachineLink, **PUBLIC_ERROR_RESPONSES, **FENCE})
    def post(self, request, makerspace_id, event_id):
        body = WorkshopMachineLinkInput(data=request.data)
        body.is_valid(raise_exception=True)
        maker = _maker(makerspace_id)
        data = body.validated_data
        link, replayed = link_machine_booking(
            request.user, maker, event_id, booking_id=data["booking_id"],
            override_reason=data.get("certification_override_reason", ""))
        row = link_row(request.user, maker, link.event, link)
        return Response({**row, "replayed": replayed}, status=200 if replayed else 201)


class EventWorkshopMachineReplacementView(_SessionOnly):
    @extend_schema(request=MachineReplacementInput, auth=[{"jwtAuth": []}],
                   summary="Replace the rejected or cancelled booking of a workshop machine link",
                   description="Creates a new booking of a machine's time through ordinary booking admission, "
                               "certification, repair gate, pricing and approval. The link and every earlier "
                               "booking, with its debt and receipts, are kept. 409 codes: `stale_context`, "
                               "`replacement_not_allowed`, `price_changed`, booking conflicts.",
                   responses={201: ReplacementOutput, **PUBLIC_ERROR_RESPONSES, **FENCE})
    def post(self, request, makerspace_id, event_id, link_id):
        body = MachineReplacementInput(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        if data["ends_at"] <= data["starts_at"]:
            raise serializers.ValidationError({"ends_at": gettext("End time must be after start time.")})
        booking = replace_machine_link(
            request.user, _maker(makerspace_id), event_id, link_id,
            expected_booking_id=data["expected_booking_id"], space_id=data["space_id"],
            member_id=data["member_id"], starts_at=data["starts_at"], ends_at=data["ends_at"],
            price_confirmation=data["price_confirmation"], note=data.get("note", ""),
            override_reason=data.get("certification_override_reason", ""))
        return Response({"booking_id": booking.pk, "replaces_booking_id": booking.replaces_id,
                         "status": booking.status}, status=201)


class WorkshopMachineUnlinked(serializers.Serializer):
    link_id = serializers.IntegerField(min_value=1, max_value=MAX_SAFE)
    unlinked = serializers.BooleanField(help_text="False when the link was already unlinked (replay).")
    unlinked_at = serializers.DateTimeField()


class EventWorkshopMachineLinkView(_SessionOnly):
    @extend_schema(request=None, auth=[{"jwtAuth": []}], summary="Unlink a workshop machine booking from the event",
                   description="Ends the link only: the booking, its machine-time charge, receipts and the link's "
                               "history are kept, and the booking may be linked again later. Needs the same event, "
                               "booking and machine authority as linking. Unlinking an already unlinked link answers "
                               "200 with `unlinked: false`. Audited as `event.workshop_machine_unlinked`.",
                   responses={200: WorkshopMachineUnlinked, **PUBLIC_ERROR_RESPONSES, **FENCE})
    def delete(self, request, makerspace_id, event_id, link_id):
        link, changed = unlink_machine_booking(request.user, _maker(makerspace_id), event_id, link_id)
        return Response({"link_id": link.pk, "unlinked": changed, "unlinked_at": link.unlinked_at})
