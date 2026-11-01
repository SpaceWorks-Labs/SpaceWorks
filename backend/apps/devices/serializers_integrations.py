"""Strict, bounded integration payloads (release 2 L10). Numbers are finite and clamped.

Clamping (not refusing) keeps one wild sensor value from dropping a whole snapshot, the
way the reference agent guide limits ranges; sizes, kinds and unknown fields are refused.
No payload carries G-code, files, printer credentials or money.
"""
import math
import re

from drf_spectacular.utils import extend_schema_serializer
from rest_framework import serializers

from apps.devices.models import MachineTypeIntegration, PrinterStatusSnapshot
from apps.devices.protocol import INTEGRATION_SCHEMA_VERSION
from apps.devices.serializers_identity import DeviceIdentitySerializer
from apps.devices.serializers_printers import ConsumptionSerializer, StrictSerializer

MAX_SPOOLS = 16
_TOKEN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def clamp(value, low, high, *, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise serializers.ValidationError(f"{label} must be a finite number.")
    return min(max(value, low), high)


class ClampedNumber(serializers.Field):
    def __init__(self, low, high, *, integer=False, **kwargs):
        self.low, self.high, self.integer = low, high, integer
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = clamp(data, self.low, self.high, label=self.field_name)
        return int(round(value)) if self.integer else round(float(value), 1)

    def to_representation(self, value):
        return value


class TemperaturesSerializer(StrictSerializer):
    nozzle = ClampedNumber(-40, 400, required=False, allow_null=True)
    bed = ClampedNumber(-40, 200, required=False, allow_null=True)
    chamber = ClampedNumber(-40, 120, required=False, allow_null=True)


class SpoolSerializer(StrictSerializer):
    slot = serializers.IntegerField(min_value=0, max_value=63)
    material = serializers.CharField(max_length=24, allow_blank=True, required=False, default="")
    colour = serializers.CharField(max_length=16, allow_blank=True, required=False, default="")
    remaining_percent = ClampedNumber(0, 100, integer=True, required=False, allow_null=True, default=None)


class StatusSnapshotSerializer(StrictSerializer):
    schema_version = serializers.ChoiceField(choices=[INTEGRATION_SCHEMA_VERSION])
    observed_at = serializers.IntegerField(min_value=1, max_value=4102444800,
                                           help_text="Unix seconds when the printer state was read.")
    state = serializers.ChoiceField(choices=PrinterStatusSnapshot.State.choices)
    progress_percent = ClampedNumber(0, 100, integer=True, required=False, allow_null=True, default=None)
    layer_current = ClampedNumber(0, 100000, integer=True, required=False, allow_null=True, default=None)
    layer_total = ClampedNumber(0, 100000, integer=True, required=False, allow_null=True, default=None)
    temperatures = TemperaturesSerializer(required=False)
    spools = SpoolSerializer(many=True, required=False, max_length=MAX_SPOOLS)
    clear_token = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")

    def validate_clear_token(self, value):
        if value and not _TOKEN.match(value):
            raise serializers.ValidationError("Use 1-64 letters, digits, '-' or '_'.")
        return value

    def validate_spools(self, value):
        slots = [row["slot"] for row in value]
        if len(slots) != len(set(slots)):
            raise serializers.ValidationError("Each spool slot may appear once.")
        return value


@extend_schema_serializer(component_name="DeviceHeartbeatRequest")
class HeartbeatSerializer(StrictSerializer):
    status_snapshot = StatusSnapshotSerializer(required=False)


@extend_schema_serializer(component_name="DeviceHeartbeatResponse")
class HeartbeatResponseSerializer(DeviceIdentitySerializer):
    status_snapshot = serializers.ChoiceField(
        choices=["stored", "stale", "throttled", "not_integrated"], required=False,
        help_text="Present only when a snapshot was sent. `not_integrated`: the integration is off "
                  "or this device is not bound to an integrated machine type; nothing was stored.")


class QueueJobSerializer(serializers.Serializer):
    service_request_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=["accepted", "in_progress"])
    on_this_machine = serializers.BooleanField()
    estimated_minutes = serializers.IntegerField(allow_null=True)
    planned_grams = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    accepted_at = serializers.DateTimeField(allow_null=True)
    started_at = serializers.DateTimeField(allow_null=True)
    printer_job_id = serializers.UUIDField(allow_null=True)


class QueueSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField()
    machine_type_id = serializers.IntegerField()
    integration_kind = serializers.CharField()
    config_schema_version = serializers.IntegerField()
    jobs = QueueJobSerializer(many=True)


class JobReportSerializer(StrictSerializer):
    """`started` names the run; `completed`/`failed` carry the existing terminal report."""

    event = serializers.ChoiceField(choices=["started", "completed", "failed"])
    external_job_id = serializers.CharField(max_length=120)
    operation_id = serializers.UUIDField(required=False)
    actual_minutes = serializers.IntegerField(min_value=0, max_value=2147483647, required=False)
    consumptions = ConsumptionSerializer(many=True, allow_empty=True, required=False)
    failure_reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    percent_complete = serializers.IntegerField(min_value=0, max_value=100, required=False, allow_null=True)
    actual_grams = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True)
    actual_quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0, required=False,
                                               allow_null=True)

    def validate(self, attrs):
        terminal = {key for key in attrs if key not in {"event", "external_job_id"}}
        if attrs["event"] == "started" and terminal:
            raise serializers.ValidationError("A started report carries only event and external_job_id.")
        if attrs["event"] != "started" and not {"operation_id", "actual_minutes", "consumptions"} <= terminal:
            raise serializers.ValidationError("A terminal report needs operation_id, actual_minutes and consumptions.")
        return attrs

    def result_payload(self):
        """The existing terminal-report body (``ResultSerializer``) this report maps to."""
        data = dict(self.initial_data)
        event = data.pop("event")
        return {**data, "outcome": event}


class TypeIntegrationCreateSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=MachineTypeIntegration.Kind.choices)
    enabled = serializers.BooleanField(default=False)
    config_schema_version = serializers.IntegerField(min_value=1, max_value=1, default=1)


class TypeIntegrationUpdateSerializer(StrictSerializer):
    enabled = serializers.BooleanField(required=False)
    config_schema_version = serializers.IntegerField(min_value=1, max_value=1, required=False)


class TypeIntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MachineTypeIntegration
        fields = ["id", "makerspace", "machine_type", "kind", "enabled", "config_schema_version",
                  "created_at", "updated_at"]
        read_only_fields = fields


class SnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrinterStatusSnapshot
        fields = ["schema_version", "state", "progress_percent", "layer_current", "layer_total",
                  "nozzle_temp_c", "bed_temp_c", "chamber_temp_c", "spools", "clear_token",
                  "observed_at", "received_at"]
        read_only_fields = fields


class IntegrationStatusSerializer(serializers.Serializer):
    device_id = serializers.UUIDField()
    device_name = serializers.CharField()
    machine_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    last_seen_at = serializers.DateTimeField(allow_null=True)
    snapshot = SnapshotSerializer(allow_null=True)
