"""OpenAPI rows for the machine analytics registry (no model serialization)."""

from rest_framework import serializers

from .serializers_reports_base import ReportRowsFieldMixin, TypedReportBaseSerializer


def _hours():
    return serializers.DecimalField(max_digits=24, decimal_places=2, allow_null=True)


class MachinePeriodRow(TypedReportBaseSerializer):
    period = serializers.DateField(allow_null=True)
    machine_id = serializers.IntegerField(allow_null=True)
    machine_name = serializers.CharField(allow_null=True)
    machine_type = serializers.CharField(allow_null=True)


class MachineUsageV2Row(MachinePeriodRow):
    measure = serializers.ChoiceField(choices=["service", "manual", "booked"])
    machine_type_id = serializers.IntegerField(allow_null=True)
    entries = serializers.IntegerField()
    service_hours = _hours()
    manual_hours = _hours()
    booked_hours = _hours()


class MachineMemberRow(serializers.Serializer):
    period = serializers.DateField()
    member_id = serializers.IntegerField(allow_null=True, help_text="Null means unattributed, never inferred from contacts.")
    measure = serializers.ChoiceField(choices=["service", "manual", "booked"])
    machine_type_id = serializers.IntegerField(allow_null=True)
    machine_type = serializers.CharField()
    entries = serializers.IntegerField()
    hours = _hours()


class MachineHeatmapRow(TypedReportBaseSerializer):
    period = serializers.DateField()
    measure = serializers.ChoiceField(choices=["service", "manual", "booked"])
    machine_type_id = serializers.IntegerField(allow_null=True)
    machine_type = serializers.CharField()
    weekday = serializers.IntegerField(min_value=0, max_value=6, help_text="Monday is zero.")
    hour = serializers.IntegerField(min_value=0, max_value=23)
    service_hours = _hours()
    manual_hours = _hours()
    booked_hours = _hours()


class MachineDowntimeRow(MachinePeriodRow):
    status = serializers.CharField(help_text="Unknown before the first recorded status event.")
    status_hours = _hours()


class MaintenanceActivityV2Row(MachinePeriodRow):
    is_active = serializers.BooleanField()
    log_count = serializers.IntegerField(allow_null=True)
    costed_log_count = serializers.IntegerField(allow_null=True)
    total_cost = _hours()
    average_cost = _hours()
    last_performed_at = serializers.DateTimeField(allow_null=True)
    average_interval_days = serializers.FloatField(allow_null=True)
    active_schedules = serializers.IntegerField(allow_null=True)
    overdue_schedules = serializers.IntegerField(allow_null=True)
    currency = serializers.CharField(allow_null=True, help_text="Unknown: legacy logs do not record currency. No cross-machine money total.")


class MachineServiceV2Row(MachinePeriodRow):
    row_kind = serializers.ChoiceField(choices=["status", "machine", "consumption", "failure"])
    submitted = serializers.IntegerField(allow_null=True)
    accepted = serializers.IntegerField(allow_null=True)
    in_progress = serializers.IntegerField(allow_null=True)
    completed = serializers.IntegerField(allow_null=True)
    collected = serializers.IntegerField(allow_null=True)
    rejected = serializers.IntegerField(allow_null=True)
    failed = serializers.IntegerField(allow_null=True)
    request_count = serializers.IntegerField(allow_null=True)
    completed_count = serializers.IntegerField(allow_null=True)
    failed_count = serializers.IntegerField(allow_null=True)
    completed_hours = _hours()
    failed_partial_hours = _hours()
    total_recorded_service_hours = _hours()
    failure_rate = serializers.FloatField(allow_null=True, help_text="Failed / (completed + failed) × 100 at terminal time.")
    measurement = serializers.CharField(allow_null=True)
    product_id = serializers.IntegerField(allow_null=True)
    product_label = serializers.CharField(allow_null=True)
    completed_amount = _hours()
    failed_partial_amount = _hours()
    total_used = _hours()
    outcome = serializers.CharField(allow_null=True)
    failed_count_amount = _hours()
    failed_grams_amount = _hours()


class ServiceQueueTimesRow(TypedReportBaseSerializer):
    period = serializers.DateField()
    queue_id = serializers.IntegerField(allow_null=True)
    queue_name = serializers.CharField()
    bucket_id = serializers.IntegerField(allow_null=True)
    stage = serializers.CharField()
    samples = serializers.IntegerField()
    median_minutes = _hours()
    p90_minutes = _hours()
    p95_minutes = _hours()


class PrinterJobsRow(MachinePeriodRow):
    state = serializers.CharField()
    outcome = serializers.CharField(allow_blank=True)
    job_count = serializers.IntegerField()


class MachineErrorsRow(MachinePeriodRow):
    severity = serializers.ChoiceField(choices=["info", "warning", "error", "critical"])
    error_count = serializers.IntegerField()


class WarrantyExpiryRow(TypedReportBaseSerializer):
    warranty_id = serializers.IntegerField()
    machine_id = serializers.IntegerField()
    machine_name = serializers.CharField()
    machine_type = serializers.CharField()
    purchased_on = serializers.DateField(allow_null=True)
    warranty_expires_on = serializers.DateField()
    days_until_expiry = serializers.IntegerField()


def _report(name, row):
    # Same envelope factory as serializers_reports_fablab; each row schema above
    # remains explicit so OpenAPI documents the public field allowlist exactly.
    return type(name, (ReportRowsFieldMixin,), {"typed_rows": row(many=True)})


MachineUsageV2ReportSerializer = _report("MachineUsageV2ReportSerializer", MachineUsageV2Row)
MachineUsageMembersReportSerializer = _report("MachineUsageMembersReportSerializer", MachineMemberRow)
MachineUsageHeatmapReportSerializer = _report("MachineUsageHeatmapReportSerializer", MachineHeatmapRow)
MachineDowntimeReportSerializer = _report("MachineDowntimeReportSerializer", MachineDowntimeRow)
MaintenanceActivityV2ReportSerializer = _report("MaintenanceActivityV2ReportSerializer", MaintenanceActivityV2Row)
MachineServiceV2ReportSerializer = _report("MachineServiceV2ReportSerializer", MachineServiceV2Row)
ServiceQueueTimesReportSerializer = _report("ServiceQueueTimesReportSerializer", ServiceQueueTimesRow)
PrinterJobsReportSerializer = _report("PrinterJobsReportSerializer", PrinterJobsRow)
MachineErrorsReportSerializer = _report("MachineErrorsReportSerializer", MachineErrorsRow)
WarrantyExpiryReportSerializer = _report("WarrantyExpiryReportSerializer", WarrantyExpiryRow)
