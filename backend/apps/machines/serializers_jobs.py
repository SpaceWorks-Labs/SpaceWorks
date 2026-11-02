"""Member-facing shapes of the uniform job flow (#140/#141): the form, a job, its timeline.

A member only ever sees their OWN job: its status label, timeline, queue position, ETA,
the quote they must answer, the outcome of a failure, and the pickup code and place.
Never another member's data, a staff note, or a storage key.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.machines.models import MachineServiceRequest
from apps.machines.service_queue_eta_serializers import ServiceRequestEtaSerializer, counts_for, eta_for

Status = MachineServiceRequest.Status
# #141 member labels; "awaiting_payment" is a quote approved but not yet paid.
LABELS = {
    Status.PENDING: "submitted", Status.CHANGES_REQUESTED: "needs_changes", Status.QUOTED: "quote_sent",
    Status.ACCEPTED: "in_queue", Status.IN_PROGRESS: "in_progress", Status.COMPLETED: "ready_to_collect",
    Status.COLLECTED: "collected", Status.UNCOLLECTED: "not_collected", Status.REJECTED: "rejected",
    Status.FAILED: "failed", Status.CANCELLED: "cancelled",
}
STEPS = (("submitted", "created_at"), ("needs_changes", "changes_requested_at"), ("quote_sent", "quoted_at"),
         ("quote_approved", "quote_approved_at"), ("in_queue", "accepted_at"), ("in_progress", "started_at"),
         ("ready_to_collect", "completed_at"), ("collected", "collected_at"), ("not_collected", "uncollected_at"),
         ("failed", "failed_at"), ("cancelled", "cancelled_at"))


class JobTypeSerializer(serializers.Serializer):
    queue_id = serializers.IntegerField()
    name = serializers.CharField()
    machine_type_id = serializers.IntegerField()
    machine_type_name = serializers.CharField()
    machine_type_slug = serializers.CharField()
    is_printer = serializers.BooleanField()
    file_groups = serializers.ListField(child=serializers.CharField())
    accepted_extensions = serializers.ListField(child=serializers.CharField())
    quotes = serializers.ChoiceField(choices=["auto", "off", "above", "always"])
    prepay = serializers.BooleanField()
    runs_unattended = serializers.BooleanField()
    max_open_jobs = serializers.IntegerField(allow_null=True)


class JobSubmitSerializer(serializers.Serializer):
    queue_id = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=200, trim_whitespace=True)
    description = serializers.CharField(required=False, allow_blank=True, max_length=4000, default="")
    source_link = serializers.URLField(required=False, allow_blank=True, default="")
    file_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), max_length=20)
    copies = serializers.IntegerField(min_value=1, max_value=999, default=1)
    needed_by = serializers.DateField(required=False, allow_null=True, default=None)
    own_material = serializers.BooleanField(default=False)
    material_note = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    member_estimate_minutes = serializers.IntegerField(required=False, allow_null=True, min_value=1,
                                                       max_value=100000, default=None)
    capability_payload = serializers.JSONField(required=False, default=None)
    material = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    color = serializers.CharField(required=False, allow_blank=True, max_length=100, default="")
    consumable_pool_id = serializers.IntegerField(required=False, allow_null=True, min_value=1, default=None)
    estimated_filament_grams = serializers.DecimalField(required=False, allow_null=True, max_digits=10,
                                                        decimal_places=2, min_value=0, default=None)
    preferred_settings = serializers.JSONField(required=False, default=None)
    acknowledgements = serializers.DictField(child=serializers.BooleanField())


class JobUploadSerializer(serializers.Serializer):
    queue_id = serializers.IntegerField(min_value=1)
    filename = serializers.CharField(max_length=240)
    content_type = serializers.CharField(max_length=128)
    kind = serializers.ChoiceField(choices=["model", "screenshot"], default="model")


class TimelineStepSerializer(serializers.Serializer):
    step = serializers.CharField()
    at = serializers.DateTimeField()


class JobQuoteLineSerializer(serializers.Serializer):
    label = serializers.CharField()
    net = serializers.CharField()


class JobQuoteSerializer(serializers.Serializer):
    total = serializers.CharField()
    currency = serializers.CharField()
    lines = JobQuoteLineSerializer(many=True)
    digest = serializers.CharField()


class MemberJobSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    public_token = serializers.UUIDField()
    makerspace_id = serializers.IntegerField()
    queue_id = serializers.IntegerField(allow_null=True)  # stage resubmit files against it
    title = serializers.CharField()
    status = serializers.CharField()
    label = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    machine_type_name = serializers.SerializerMethodField()
    machine_name = serializers.CharField(source="run_machine_name")
    position = serializers.SerializerMethodField()
    eta = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()
    changes_message = serializers.CharField()
    quote = serializers.SerializerMethodField()
    quote_expires_at = serializers.DateTimeField(allow_null=True)
    awaiting_payment = serializers.SerializerMethodField()
    reason = serializers.SerializerMethodField()
    fail_code = serializers.CharField()
    failure_outcome = serializers.CharField()
    pickup_code = serializers.SerializerMethodField()
    pickup_location = serializers.CharField()
    copies = serializers.IntegerField()
    needed_by = serializers.DateField(allow_null=True)
    created_at = serializers.DateTimeField()

    def get_label(self, row) -> str:
        if row.status == Status.QUOTED and row.quote_approved_at:
            return "awaiting_payment"
        return LABELS.get(row.status, row.status)

    def get_can_cancel(self, row) -> bool:
        from apps.machines.service_workflow_cancel import owner_may_cancel
        from apps.makerspaces.platform import module_enabled
        cache = self.context.setdefault("service_on", {})
        if row.makerspace_id not in cache:
            cache[row.makerspace_id] = module_enabled(row.makerspace, "machine_service")
        return owner_may_cancel(row, self.context.get("user"), service_enabled=cache[row.makerspace_id])

    def get_machine_type_name(self, row) -> str:
        return (row.queue.machine_type if row.queue_id else row.bucket.machine.machine_type).name

    def get_position(self, row) -> int | None:
        counts = counts_for(self, row) if row.status == Status.ACCEPTED else None
        return counts["position"] if counts else None

    @extend_schema_field(ServiceRequestEtaSerializer(allow_null=True))
    def get_eta(self, row):
        return eta_for(self, row) if row.status in (Status.ACCEPTED, Status.IN_PROGRESS) else None

    @extend_schema_field(TimelineStepSerializer(many=True))
    def get_timeline(self, row):
        return [{"step": step, "at": getattr(row, field)} for step, field in STEPS if getattr(row, field)]

    @extend_schema_field(JobQuoteSerializer(allow_null=True))
    def get_quote(self, row):
        snapshot = row.quote_snapshot or None
        if not snapshot or row.status not in (Status.QUOTED, Status.ACCEPTED, Status.IN_PROGRESS, Status.COMPLETED):
            return None
        from apps.machines.service_workflow_review import member_quote
        return member_quote(snapshot)

    def get_awaiting_payment(self, row) -> bool:
        return bool(row.status == Status.QUOTED and row.quote_approved_at and row.prepay)

    def get_reason(self, row) -> str:
        return row.reason if row.status in (Status.REJECTED, Status.FAILED) else ""

    def get_pickup_code(self, row) -> str:
        return row.pickup_code if row.status == Status.COMPLETED else ""

