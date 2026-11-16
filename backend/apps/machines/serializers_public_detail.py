from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from django.db.models import Sum
from apps.accounts import rbac
from .models import MachineUsageEntry

from .serializers_public_machines import PublicMachineSerializer
from .public_detail import queue_estimate, training
from .service_queue_eta_serializers import MachineQueueSummarySerializer


class PublicQueueEstimateSerializer(MachineQueueSummarySerializer):
    """Legacy ``length``/``eta_minutes`` keys kept; ``eta_minutes`` is now the machine's
    simulated final free-at offset (never total minutes divided by machine count)."""


class PublicMachineDetailSerializer(PublicMachineSerializer):
    machine_type = serializers.SerializerMethodField()
    id = serializers.IntegerField(read_only=True)

    @extend_schema_field({"type": "string", "format": "decimal"})
    def get_usage_hours(self, machine):
        total = rbac.scope_verified_tenant(MachineUsageEntry.objects.all(), machine.makerspace,
            field="machine__makerspace_id").filter(machine=machine).aggregate(total=Sum("hours"))["total"] or 0
        return f"{total:.2f}"

    @extend_schema_field({"type": "object", "properties": {"id": {"type": "integer"}, "name": {"type": "string"}, "icon": {"type": "string"}}})
    def get_machine_type(self, machine):
        return {"id": machine.machine_type_id, "name": machine.machine_type.name, "icon": machine.machine_type.icon}
    status_since = serializers.DateTimeField(read_only=True)
    training_required = serializers.SerializerMethodField()
    expected_back_on = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_expected_back_on(self, machine):
        """While out of service: the DATE staff expect it back (downtime ledger). No reason text."""
        if machine.status not in ("maintenance", "offline"):
            return None
        from .models import MachineDowntime
        row = MachineDowntime.objects.filter(machine=machine, ended_at__isnull=True,
                                             expected_back_at__isnull=False).first()
        if row is None:
            return None
        from apps.makerspaces.local_time import to_local
        return to_local(machine.makerspace, row.expected_back_at).date()
    queue = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_training_required(self, machine):
        return training(machine)

    @extend_schema_field(PublicQueueEstimateSerializer(allow_null=True))
    def get_queue(self, machine):
        # The view supplies one page-level summary map; detail falls back to one snapshot.
        return queue_estimate(machine, self.context.get("queue_summaries"))
