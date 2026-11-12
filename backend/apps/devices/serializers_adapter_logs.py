"""Read-only staff list shapes for adapter access decisions, usage records and a binding's jobs.

No credential digest, PIN, token or member contact detail is ever included: a member appears as an id only.
"""
from rest_framework import serializers

from apps.devices.models import AdapterAccessLog, AdapterUsageLog
from apps.devices.models_printers import PrinterJob


class AccessDecisionSerializer(serializers.ModelSerializer):
    session_id = serializers.IntegerField(source="session_id_snapshot", read_only=True)

    class Meta:
        model = AdapterAccessLog
        fields = ("id", "binding", "member", "credential_type", "allowed", "reason", "session_id", "created_at")
        read_only_fields = fields


class UsageRecordSerializer(serializers.ModelSerializer):
    session_id = serializers.IntegerField(source="session_id_snapshot", read_only=True)

    class Meta:
        model = AdapterUsageLog
        fields = ("id", "binding", "operation_id", "session_id", "started_at", "ended_at", "active_minutes",
                  "idle_minutes", "outcome", "error_code", "consumptions", "created_at")
        read_only_fields = fields


class BindingJobSerializer(serializers.ModelSerializer):
    service_request_id = serializers.IntegerField(source="service_request_id_snapshot", read_only=True)
    command_status = serializers.CharField(source="command.status", read_only=True)
    command_attempts = serializers.IntegerField(source="command.attempts", read_only=True)
    command_error = serializers.CharField(source="command.last_error_code", read_only=True)

    class Meta:
        model = PrinterJob
        fields = ("id", "service_request_id", "service_request_name", "machine_name", "state", "telemetry_state",
                  "progress_percent", "telemetry_at", "outcome", "actual_minutes", "percent_complete", "failure_reason",
                  "reported_at", "applied_at", "created_at", "command_status", "command_attempts", "command_error")
        read_only_fields = fields
