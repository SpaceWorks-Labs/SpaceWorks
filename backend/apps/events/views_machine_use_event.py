"""The event page's Machine use section and the organiser's cost decision (decision 342)."""
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.view_helpers import PUBLIC_ERROR_RESPONSES
from apps.makerspaces.guards import require_module

from . import event_authority, event_permissions, machine_use_costs
from .machine_use_summary import rows_for, totals_for
from .models import Event
from .models_machine_use import MachineEventCostApproval

TAGS = ["Machine use for events"]


class MachineUseConsumableSerializer(serializers.Serializer):
    label = serializers.CharField(allow_blank=True)
    unit = serializers.CharField()
    quantity = serializers.CharField()


class MachineUseChargeSerializer(serializers.Serializer):
    amount = serializers.CharField()
    currency = serializers.CharField()
    status = serializers.CharField()


class MachineUseRowSerializer(serializers.Serializer):
    link_id = serializers.IntegerField()
    kind = serializers.ChoiceField(choices=["session", "request", "booking"])
    subject_id = serializers.IntegerField()
    title = serializers.CharField()
    machine_type = serializers.CharField()
    person = serializers.CharField(allow_blank=True)
    minutes = serializers.IntegerField()
    consumables = MachineUseConsumableSerializer(many=True)
    source = serializers.CharField()
    created_at = serializers.DateTimeField()
    charge = MachineUseChargeSerializer(allow_null=True)
    cost_decision = serializers.CharField(allow_null=True)


class MachineUseTotalsSerializer(serializers.Serializer):
    sessions = serializers.IntegerField()
    bookings = serializers.IntegerField()
    requests = serializers.IntegerField()
    minutes = serializers.IntegerField()
    consumables = MachineUseConsumableSerializer(many=True)
    charged = serializers.DictField(child=serializers.CharField())
    approved_to_event = serializers.DictField(child=serializers.CharField())


class MachineUseSerializer(serializers.Serializer):
    rows = MachineUseRowSerializer(many=True)
    totals = MachineUseTotalsSerializer()
    can_decide_costs = serializers.BooleanField(
        help_text="An organiser may approve costs and event charges are tracked.")


class CostDecisionWrite(serializers.Serializer):
    decision = serializers.ChoiceField(choices=MachineEventCostApproval.Decision.values)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


def _event(request, makerspace_id, event_id, permission):
    event = get_object_or_404(Event.objects.select_related("makerspace"), pk=event_id, makerspace_id=makerspace_id)
    require_module(event.makerspace, "machines")
    if not event_authority.can(request.user, event, permission):
        raise NotFound()
    return event


class EventMachineUseView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Machine use logged for this event", responses={
        200: MachineUseSerializer, **PUBLIC_ERROR_RESPONSES})
    def get(self, request, makerspace_id, event_id):
        event = _event(request, makerspace_id, event_id, event_permissions.MANAGE_REGISTRATIONS)
        rows = rows_for(event)
        decide = machine_use_costs.finance_on(event.makerspace) and event_authority.can(
            request.user, event, event_permissions.EDIT_DETAILS)
        return Response({"rows": rows, "totals": totals_for(rows), "can_decide_costs": decide})


class EventMachineUseCostView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=TAGS, summary="Approve or withdraw charging one item's cost to the event",
                   description="Records the organiser's decision only; the member's own charge is not changed.",
                   request=CostDecisionWrite, responses={204: None, **PUBLIC_ERROR_RESPONSES})
    def post(self, request, makerspace_id, event_id, link_id):
        event = _event(request, makerspace_id, event_id, event_permissions.EDIT_DETAILS)
        data = CostDecisionWrite(data=request.data)
        data.is_valid(raise_exception=True)
        machine_use_costs.decide(request.user, event, link_id, data.validated_data["decision"],
                                 data.validated_data["note"])
        return Response(status=204)
