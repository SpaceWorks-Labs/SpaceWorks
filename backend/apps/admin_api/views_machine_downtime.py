"""A machine's downtime ledger and lockout state (machines D6/D7, MT5/MT6), behind
`machines.maintenance`."""

from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admin_api.machine_access import resolve_machine
from apps.admin_api.permissions import IsActiveStaff
from apps.hardware_requests.exceptions import ErrorSerializer
from apps.machines import access, downtime
from apps.machines.lockout import blocking_schedules
from apps.machines.models import MachineDowntime
from apps.makerspaces.folded_capabilities import require_capability

ERRORS = {code: ErrorSerializer for code in (400, 401, 403, 404)}


class DowntimeRowSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineDowntime
        fields = ["id", "kind", "reason", "expected_back_at", "started_at", "ended_at"]


class DowntimeSummarySerializer(serializers.Serializer):
    days = serializers.IntegerField()
    uptime_percent = serializers.FloatField()
    periods = serializers.IntegerField()
    mean_hours_to_repair = serializers.FloatField(allow_null=True)


class DowntimeSerializer(serializers.Serializer):
    summary = DowntimeSummarySerializer()
    periods = DowntimeRowSerializer(many=True)


class DowntimeUpdateSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, max_length=300, allow_blank=True)
    expected_back_at = serializers.DateTimeField(required=False, allow_null=True)


class LockoutScheduleSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    description = serializers.CharField()
    next_due = serializers.DateField()


class LockoutSerializer(serializers.Serializer):
    locked = serializers.BooleanField()
    schedules = LockoutScheduleSerializer(many=True)


def _machine(request, pk, *, manage=False):
    machine = resolve_machine(request.user, pk)
    require_capability(machine.makerspace_id, downtime.FEATURE)
    allowed = access.can_manage_machine(request.user, machine) if manage else access.can_operate_machine(
        request.user, machine)
    if not allowed:
        raise PermissionDenied()
    return machine


class MachineDowntimeView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machines"], summary="Downtime periods and uptime for a machine",
                   responses={200: DowntimeSerializer, **ERRORS})
    def get(self, request, pk):
        machine = _machine(request, pk)
        rows = MachineDowntime.objects.filter(machine=machine)[:50]
        return Response(DowntimeSerializer({"summary": downtime.summary(machine), "periods": rows}).data)

    @extend_schema(tags=["Admin machines"], summary="Update the open downtime's reason or expected-back time",
                   request=DowntimeUpdateSerializer, responses={200: DowntimeSerializer, **ERRORS})
    @transaction.atomic
    def patch(self, request, pk):
        machine = _machine(request, pk, manage=True)
        payload = DowntimeUpdateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        downtime.update_open(machine, request.user, **payload.validated_data)
        rows = MachineDowntime.objects.filter(machine=machine)[:50]
        return Response(DowntimeSerializer({"summary": downtime.summary(machine), "periods": rows}).data)


class MachineLockoutView(APIView):
    permission_classes = [IsActiveStaff]

    @extend_schema(tags=["Admin machines"], summary="Is this machine locked out by overdue safety maintenance?",
                   responses={200: LockoutSerializer, **ERRORS})
    def get(self, request, pk):
        schedules = blocking_schedules(_machine(request, pk))
        return Response(LockoutSerializer({"locked": bool(schedules), "schedules": schedules}).data)
