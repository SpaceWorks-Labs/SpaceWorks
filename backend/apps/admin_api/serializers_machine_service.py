"""Staff API serializers for machine service requests."""

from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.machines.event_use import event_summary
from apps.machines.models import MachineServiceRequest
from apps.machines.serializers_sessions import MachineEventSummarySerializer
from apps.machines import job_risk
from apps.machines.service_queue_eta_serializers import ServiceRequestEtaSerializer, eta_for
from apps.payments.models import Payment
from apps.payments.serializers import StaffPaymentSerializer


class ServiceRequesterSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    display = serializers.SerializerMethodField()

    def get_display(self, user) -> str:
        return user.get_full_name().strip() or user.username


class ServiceMachineSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)


class ServiceFileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    kind = serializers.CharField(read_only=True)
    original_filename = serializers.CharField(read_only=True)
    content_type = serializers.CharField(read_only=True)
    size_bytes = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    attached_at = serializers.DateTimeField(read_only=True)


class ServiceConsumptionSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    machine_consumable_id = serializers.IntegerField(read_only=True)
    measurement = serializers.CharField(read_only=True)
    product_id = serializers.IntegerField(read_only=True, allow_null=True)
    label = serializers.CharField(read_only=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    outcome = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


# The uniform job flow's staff-visible columns (#140-#142). The pickup code is NOT here:
# staff type or scan what the collector shows.
JOB_FIELDS = (
    "queued_at", "urgent", "urgent_reason", "needed_by", "copies", "own_material", "material_note",
    "member_estimate_minutes", "preassigned_machine_id", "batch_id", "changes_requested_at", "changes_code",
    "changes_message", "member_note", "reject_code", "quote_snapshot", "quoted_at", "quote_expires_at",
    "quote_approved_at", "prepay", "fail_code", "fail_fault", "failure_outcome", "auto_requeue_count",
    "pickup_location", "pickup_reminders_sent", "uncollected_at", "collected_by_name", "reprint_of_id",
)


class MachineServiceRequestSerializer(serializers.ModelSerializer):
    preassigned_machine_id = serializers.IntegerField(read_only=True, allow_null=True)
    batch_id = serializers.IntegerField(read_only=True, allow_null=True)
    reprint_of_id = serializers.IntegerField(read_only=True, allow_null=True)
    quote_snapshot = serializers.JSONField(read_only=True, allow_null=True)
    machine = ServiceMachineSerializer(source="bucket.machine", read_only=True)
    assigned_machine = ServiceMachineSerializer(read_only=True)
    requester = ServiceRequesterSerializer(read_only=True)
    bucket_id = serializers.IntegerField(read_only=True)
    queue_id = serializers.IntegerField(read_only=True)
    machine_type = serializers.SerializerMethodField()
    capability_payload = serializers.JSONField(read_only=True)
    metering_unit = serializers.CharField(read_only=True, allow_null=True)
    planned_quantity = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, allow_null=True)
    reserved_quantity = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, allow_null=True)
    actual_consumed_quantity = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, allow_null=True)
    planned_grams = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    reserved_grams = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    actual_consumed_grams = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    payment = serializers.SerializerMethodField()
    event = serializers.SerializerMethodField(help_text="The event this job is logged for (decision 342), or null.")
    run_machine_model = serializers.CharField(read_only=True)
    files = ServiceFileSerializer(many=True, read_only=True)
    consumptions = ServiceConsumptionSerializer(many=True, read_only=True)
    eta = serializers.SerializerMethodField()
    at_risk_reasons = serializers.SerializerMethodField(
        help_text="Why the job may miss the member's needed-by date (#142 OQ-6); empty when on track. "
                  "A flag only: the date never reorders the queue.")

    class Meta:
        model = MachineServiceRequest
        fields = (
            "id", "bucket_id", "queue_id", "machine_type", "machine", "assigned_machine", "requester",
            "requester_name", "contact_email", "contact_phone", "title",
            "description", "source_link", "status", "reason", "estimated_minutes",
            "actual_minutes", "fail_percent_complete", "accepted_at", "started_at",
            "completed_at", "failed_at", "collected_at", "cancelled_at", "created_at", "updated_at",
            "capability_payload", "metering_unit", "planned_quantity", "reserved_quantity", "actual_consumed_quantity", "planned_grams", "reserved_grams", "actual_consumed_grams", "payment", "run_machine_model", "files", "consumptions", "eta",
            "at_risk_reasons", "event", *JOB_FIELDS,
        )
        read_only_fields = fields

    @extend_schema_field(MachineEventSummarySerializer(allow_null=True))
    def get_event(self, obj):
        return event_summary(obj)

    @extend_schema_field(ServiceRequestEtaSerializer(allow_null=True))
    def get_eta(self, obj):
        # Context-only: list/detail/action responses pass one batched snapshot.
        value = eta_for(self, obj)
        self.context.setdefault("_eta_by_id", {})[obj.pk] = value
        return value

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=job_risk.REASONS)))
    def get_at_risk_reasons(self, obj):
        return job_risk.for_serializer(self, obj, self.context.get("_eta_by_id", {}).get(obj.pk))

    def get_machine_type(self, obj) -> str:
        if obj.queue_id:
            return obj.queue.machine_type.slug
        machine = obj.assigned_machine or (obj.bucket.machine if obj.bucket_id else None)
        return machine.machine_type.slug if machine else ""

    @extend_schema_field(StaffPaymentSerializer(allow_null=True))
    def get_payment(self, obj):
        payment_map = self.context.get("payments_by_subject_id")
        payment = payment_map.get(obj.pk) if payment_map is not None else Payment.objects.filter(
            makerspace_id=obj.makerspace_id,
            subject_type=Payment.SubjectType.MACHINE_SERVICE_REQUEST,
            subject_id=obj.pk,
        ).first()
        return StaffPaymentSerializer(
            payment,
            # Keyed `(subject_type, subject_id)` and valued `(label, makerspace_id,
            # member_id)` to match what `resolve_subject_labels` returns. A bare `obj.pk`
            # key never matched, so this surface had always silently fallen back to the
            # generic display -- and now that machine-service deliberately snapshots no
            # `subject_label` (the title is member-typed free text), this is the only place
            # left that names the job. Staff already read the title on this same row.
            context={
                "payment_subject_labels": {
                    (Payment.SubjectType.MACHINE_SERVICE_REQUEST, obj.pk): (
                        obj.title,
                        obj.makerspace_id,
                        None,
                    )
                }
            },
        ).data if payment else None


class MachineServiceSubmitSerializer(serializers.Serializer):
    requester_id = serializers.IntegerField(min_value=1)
    machine_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True)
    source_link = serializers.URLField(required=False, allow_blank=True)
    requester_name = serializers.CharField(required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    capability_payload = serializers.JSONField(required=False)
    certification_override_reason = serializers.CharField(
        required=False, allow_blank=True, max_length=1000, write_only=True,
        help_text="Submits the job for a member who lacks a required certification. Honoured only "
        "for staff with authority over the machine type; every override is audited.",
    )


class ServiceAcceptSerializer(serializers.Serializer):
    estimated_minutes = serializers.IntegerField(required=False, min_value=0)
    planned_grams = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"))
    note = serializers.CharField(required=False, allow_blank=True)
    override_length = serializers.BooleanField(required=False, default=False,
                                               help_text="Accept a job longer than the type allows.")


REJECT_CODES = ("not_allowed_content", "ip_concern", "not_eligible", "for_someone_else",
                "better_made_another_way", "too_large", "other")
FAIL_CODES = ("adhesion", "nozzle_jam", "material_ran_out", "machine_fault", "power_cut", "operator_error",
              "file_problem", "material_defect", "other")


class ServiceRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
    code = serializers.ChoiceField(required=False, allow_blank=True, default="", choices=REJECT_CODES)


class ServiceCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500, trim_whitespace=True)
    consumed_quantity = serializers.DecimalField(
        required=False, allow_null=True, max_digits=12, decimal_places=2, min_value=Decimal("0"),
        help_text=("Material used so far by a RUNNING job, in its consumable hold's unit (0 to the held "
                   "amount). It stays taken from stock and is costed; nothing is charged. Empty or 0 "
                   "releases the whole hold."),
    )


class ServiceStartSerializer(serializers.Serializer):
    machine_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    estimated_minutes = serializers.IntegerField(required=False, min_value=0)
    consumable_pool_id = serializers.IntegerField(required=False, min_value=1)
    planned_grams = serializers.DecimalField(
        required=False, max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )
    planned_quantity = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class ServiceConsumptionInputSerializer(serializers.Serializer):
    machine_consumable_id = serializers.IntegerField(min_value=1)
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0.01")
    )


class ServiceCompleteSerializer(serializers.Serializer):
    pickup_location = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")
    actual_minutes = serializers.IntegerField(min_value=0)
    actual_grams = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"))
    actual_quantity = serializers.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=Decimal("0"))
    consumptions = ServiceConsumptionInputSerializer(many=True, required=False, default=list)
    # Decision 341: actual use of the type's profile consumables, by key.
    profile_consumptions = serializers.ListField(child=serializers.DictField(), required=False, max_length=32,
                                                 default=list)


class ServiceFailSerializer(ServiceCompleteSerializer):
    reason = serializers.CharField(allow_blank=False, trim_whitespace=True)
    percent_complete = serializers.IntegerField(min_value=0, max_value=100)
    code = serializers.ChoiceField(required=False, allow_blank=True, default="", choices=FAIL_CODES)
    fault = serializers.ChoiceField(required=False, allow_blank=True, default="", choices=("space", "member"),
                                    help_text="space: re-run free at the front; member: the type's failure "
                                              "charge applies.")

    def validate(self, attrs):
        attrs.pop("pickup_location", None)
        return attrs


class ServiceCollectSerializer(serializers.Serializer):
    pickup_code = serializers.CharField(required=False, allow_blank=True, max_length=16, default="")
    collector_name = serializers.CharField(required=False, allow_blank=True, max_length=120, default="")


class EmptyServiceActionSerializer(serializers.Serializer):
    pass


class ServiceFilePresignSerializer(serializers.Serializer):
    filename = serializers.CharField(max_length=255)
    content_type = serializers.CharField(max_length=128)


class ServiceFileUploadSerializer(serializers.Serializer):
    url = serializers.URLField()
    method = serializers.CharField(required=False)
    fields = serializers.DictField(required=False)
    headers = serializers.DictField(required=False)


class ServiceFilePresignResponseSerializer(serializers.Serializer):
    file_id = serializers.IntegerField()
    upload = ServiceFileUploadSerializer()


class ServiceFileFinalizeSerializer(serializers.Serializer):
    file_id = serializers.IntegerField(min_value=1)


class ServiceFileFinalizeResponseSerializer(serializers.Serializer):
    file_id = serializers.IntegerField()


class ServiceFileUrlSerializer(serializers.Serializer):
    url = serializers.URLField()
