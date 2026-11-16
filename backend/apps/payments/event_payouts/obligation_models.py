"""Permanent obligations retain inert source provenance after Events removal."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from .model_base import Immutable, RequiredPii


class EventPayoutObligation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="event_payout_obligations")
    owner_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="event_payout_obligations")
    event = models.ForeignKey("events.Event", on_delete=models.SET_NULL, null=True, related_name="payout_obligations")
    event_id_snapshot = models.PositiveBigIntegerField()
    event_title_snapshot = models.CharField(max_length=200)
    source_kind = models.CharField(max_length=24, default="event_reimbursement", choices=[("event_reimbursement", "event_reimbursement")])
    source_uuid = models.UUIDField()
    source_decision_revision = models.PositiveBigIntegerField()
    domain_coordination_state = models.CharField(max_length=8, default="attached", choices=[(v, v) for v in ("attached", "detached")])
    currency = models.CharField(max_length=3)
    approved_minor = models.PositiveBigIntegerField()
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    current_revision = models.ForeignKey("payments.EventPayoutObligationRevision", on_delete=models.SET_NULL, null=True, related_name="+")
    eligibility_status = models.CharField(max_length=24, default="needs_acknowledgement", choices=[(v, v) for v in (
        "eligible", "held", "needs_acknowledgement")])
    eligibility_revision = models.PositiveBigIntegerField(default=1)
    eligibility_evidence = models.JSONField(default=dict)
    hold_reason_code = models.CharField(max_length=64, blank=True)
    state = models.CharField(max_length=12, default="open", choices=[(v, v) for v in ("open", "settled", "cancelled")])
    terminal_financial_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "payments"
        constraints = [
            models.UniqueConstraint(fields=("source_kind", "source_uuid"), name="payout_unique_source"),
            models.CheckConstraint(condition=models.Q(version__gte=1, eligibility_revision__gte=1), name="payout_obligation_versions"),
            models.CheckConstraint(condition=(~models.Q(state="cancelled") | models.Q(approved_minor=0)), name="payout_cancelled_zero"),
        ]


class EventPayoutObligationRevision(RequiredPii, Immutable):
    mandatory_pii_fields = ("decision_summary", "cancellation_note")
    obligation = models.ForeignKey(EventPayoutObligation, on_delete=models.CASCADE, related_name="revisions")
    sequence = models.PositiveBigIntegerField()
    previous_revision = models.OneToOneField("self", on_delete=models.CASCADE, null=True, related_name="next_revision")
    kind = models.CharField(max_length=12, choices=[(v, v) for v in ("decision", "cancellation")])
    approved_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    decision_uuid = models.UUIDField(null=True)
    decision_revision = models.PositiveBigIntegerField(null=True)
    reason_code = models.CharField(max_length=64)
    cancellation_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    operation_id = models.UUIDField(unique=True)
    command_digest = models.CharField(max_length=64)
    decision_summary_schema_version = models.PositiveSmallIntegerField(default=1)
    # Canonical JSON is serialized to text before the shared scoped envelope mapper.
    # G must register BOTH fields with encryption_required=True before any writes.
    decision_summary = models.TextField()

    class Meta:
        app_label = "payments"
        constraints = [
            models.UniqueConstraint(fields=("obligation", "sequence"), name="payout_revision_sequence_unique"),
            models.UniqueConstraint(fields=("decision_uuid", "decision_revision"), condition=models.Q(kind="decision"), name="payout_decision_origin_unique"),
            models.CheckConstraint(condition=(models.Q(kind="decision", decision_uuid__isnull=False,
                decision_revision__isnull=False) | models.Q(kind="cancellation", approved_minor=0,
                decision_uuid__isnull=True, decision_revision__isnull=True)), name="payout_revision_kind_shape"),
            models.CheckConstraint(condition=(models.Q(sequence=1, previous_revision__isnull=True)
                | models.Q(sequence__gt=1, previous_revision__isnull=False)), name="payout_revision_chain_shape"),
        ]
