"""Event equipment time-window availability and bulk per-person planning (decision 221b)."""
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authentication import SpaceWorksJWTAuthentication
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES

from .equipment_window import (
    MAX_PARTICIPANTS, MAX_PRODUCTS, event_window, plan_for_participants, planning_event, window_rows,
)

SAFE = 9007199254740991
FENCE = {423: OpenApiResponse(ErrorSerializer, description="Tenant write fence is closed.")}


class WindowSerializer(serializers.Serializer):
    class Meta:
        ref_name = "EventEquipmentWindow"

    starts_at = serializers.DateTimeField()
    return_due_at = serializers.DateTimeField(help_text="Event end plus the event's return window.")


class WindowRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    event_only = serializers.BooleanField()
    status = serializers.ChoiceField(choices=["available", "limited", "unavailable"])
    free = serializers.IntegerField(required=False, help_text="Units free for the whole window; inventory-view staff only.")
    committed = serializers.IntegerField(required=False)
    back_before_window = serializers.IntegerField(required=False)
    lendable = serializers.IntegerField(required=False)


class AvailabilitySerializer(serializers.Serializer):
    window = WindowSerializer()
    equipment_return_hours = serializers.IntegerField(allow_null=True)
    counts_visible = serializers.BooleanField()
    results = WindowRowSerializer(many=True)


class _SessionOnly(APIView):
    authentication_classes = [SpaceWorksJWTAuthentication]
    permission_classes = [IsActiveStaff]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if getattr(request, "api_client", None) or getattr(request, "person_credential", None):
            raise PermissionDenied(gettext("This endpoint requires a staff session."))


class EventEquipmentAvailabilityView(_SessionOnly):
    @extend_schema(
        tags=["Admin events"], auth=[{"jwtAuth": []}], summary="Equipment free during the event window",
        parameters=[OpenApiParameter("product_ids", str, OpenApiParameter.QUERY, required=True,
                                     description=f"Comma-separated product ids, at most {MAX_PRODUCTS}.")],
        description="Reserved versus free units between the event start and the time its loans fall due, "
                    "computed by the inventory availability owner (read-only, reserves nothing). Needs event "
                    "manage_registrations; exact counts only for staff who also hold view_inventory, everyone "
                    "else gets `status`.",
        responses={200: AvailabilitySerializer, **PUBLIC_ERROR_RESPONSES})
    def get(self, request, makerspace_id, event_id):
        event = planning_event(request.user, makerspace_id, event_id)
        raw = request.query_params.get("product_ids", "")
        try:
            ids = [int(part) for part in raw.split(",") if part.strip()]
        except ValueError:
            raise ValidationError({"product_ids": gettext("Invalid product ids.")}) from None
        if not ids or len(ids) > MAX_PRODUCTS or any(not 0 < pk <= SAFE for pk in ids):
            raise ValidationError({"product_ids": gettext("Provide between 1 and %(n)d product ids.") % {"n": MAX_PRODUCTS}})
        rows, _figures, counts = window_rows(request.user, event, ids)
        starts, due = event_window(event)
        return Response({"window": {"starts_at": starts, "return_due_at": due},
                         "equipment_return_hours": event.equipment_return_hours,
                         "counts_visible": counts, "results": rows})


class PlanLineSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1, max_value=SAFE)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class PlanParticipantSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField(min_value=1, max_value=SAFE)
    lines = PlanLineSerializer(many=True, required=False, max_length=20, help_text=(
        "Replaces the default lines for this person, for example one accountable lead holding shared units."))


class EventEquipmentPlanSerializer(serializers.Serializer):
    operation_id = serializers.UUIDField(help_text="Idempotency key; each participant derives a stable one from it.")
    requested_for = serializers.CharField(max_length=500, allow_blank=True, default="")
    lines = PlanLineSerializer(many=True, max_length=20, help_text="Default lines for every participant.")
    participants = PlanParticipantSerializer(many=True, min_length=1, max_length=MAX_PARTICIPANTS)
    dry_run = serializers.BooleanField(default=False, help_text="Only report window totals; create nothing.")

    def validate(self, attrs):
        regs = [row["registration_id"] for row in attrs["participants"]]
        if len(regs) != len(set(regs)):
            raise serializers.ValidationError(gettext("Duplicate participants."))
        for person in attrs["participants"]:
            person["lines"] = person.get("lines") or []
            chosen = person["lines"] or attrs["lines"]
            if not chosen:
                raise serializers.ValidationError(gettext("Every participant needs at least one line."))
            ids = [line["product_id"] for line in chosen]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError(gettext("Duplicate products in a line list."))
        return attrs


class PlanTotalSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    requested = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["ok", "short"], help_text="Advisory; accept and issue still decide.")
    free = serializers.IntegerField(required=False)


class PlanResultSerializer(serializers.Serializer):
    registration_id = serializers.IntegerField()
    outcome = serializers.ChoiceField(choices=["created", "replayed", "error"])
    request_id = serializers.IntegerField(required=False)
    status = serializers.CharField(required=False)
    code = serializers.CharField(required=False, help_text="For example not_found, event_only_product, lock_busy.")


class EventEquipmentPlanResponse(serializers.Serializer):
    dry_run = serializers.BooleanField()
    totals = PlanTotalSerializer(many=True)
    results = PlanResultSerializer(many=True)


class EventEquipmentPlanView(_SessionOnly):
    @extend_schema(
        tags=["Admin events"], auth=[{"jwtAuth": []}], request=EventEquipmentPlanSerializer,
        summary="Plan equipment for several event participants at once",
        description="Creates one ordinary pending request per participant through the contextual staff intake, "
                    "each bound to that participant's registration, so every issue still records one accountable "
                    "borrower. Nothing is reserved here; accept, reserve and issue stay in the request workflow. "
                    "Partial success is reported per participant. Replaying the same operation_id is idempotent.",
        responses={200: EventEquipmentPlanResponse, **PUBLIC_ERROR_RESPONSES, **FENCE})
    def post(self, request, makerspace_id, event_id):
        event = planning_event(request.user, makerspace_id, event_id)  # switches answer before the body is read
        body = EventEquipmentPlanSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        data = body.validated_data
        return Response(plan_for_participants(
            request.user, event, operation_id=data["operation_id"], requested_for=data["requested_for"],
            lines=data["lines"], participants=data["participants"], dry_run=data["dry_run"]))
