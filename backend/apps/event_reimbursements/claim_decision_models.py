"""Finance decisions are separate from nonfinancial reviewer recommendations."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Immutable


class ClaimDecision(ScopedPiiModelMixin, Immutable):
    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    claim = models.ForeignKey("event_reimbursements.ReimbursementClaim", on_delete=models.CASCADE, related_name="decisions")
    revision = models.ForeignKey("event_reimbursements.ClaimRevision", on_delete=models.CASCADE, related_name="decisions")
    sequence = models.PositiveBigIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    outcome = models.CharField(max_length=20, choices=[(v, v) for v in (
        "approved", "partially_approved", "rejected", "returned_for_info")])
    approved_total_minor = models.PositiveBigIntegerField()
    award_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    attendance_checkin_event_id = models.PositiveBigIntegerField(null=True)
    attendance_revision = models.PositiveBigIntegerField()
    project_snapshot_ref = models.UUIDField(null=True)
    decided_at = models.DateTimeField()
    reason_code = models.CharField(max_length=64)
    reason = models.TextField(blank=True)
    core_obligation_id = models.UUIDField(null=True)
    core_decision_revision = models.PositiveBigIntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("claim", "sequence"), name="reimb_decision_sequence_unique"),
            models.CheckConstraint(condition=models.Q(approved_total_minor__lte=models.F("award_minor")),
                                   name="reimb_decision_award_bound"),
        ]


class ClaimLineDecision(ScopedPiiModelMixin, Immutable):
    decision = models.ForeignKey(ClaimDecision, on_delete=models.CASCADE, related_name="line_decisions")
    line = models.ForeignKey("event_reimbursements.ClaimLine", on_delete=models.CASCADE, related_name="decisions")
    approved_minor = models.PositiveBigIntegerField()
    reason_code = models.CharField(max_length=64)
    reason = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("decision", "line"), name="reimb_line_decision_unique")]


class ClaimAppeal(ScopedPiiModelMixin, models.Model):
    claim = models.OneToOneField("event_reimbursements.ReimbursementClaim", on_delete=models.CASCADE, related_name="appeal")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField()
    statement = models.TextField()
    original_decision = models.ForeignKey(ClaimDecision, on_delete=models.CASCADE, related_name="appeals")
    resolved_decision = models.ForeignKey(ClaimDecision, on_delete=models.SET_NULL, null=True, related_name="+")
    resolved_by_cancellation_revision_id = models.PositiveBigIntegerField(null=True)
    resolution_at = models.DateTimeField(null=True)

    # Submission evidence is immutable; resolution pointers are a one-way workflow
    # projection. G's DB guard must enforce that narrower shape, not freeze the
    # entire row (which would make resolving an appeal impossible).


class ClaimScreeningReview(ScopedPiiModelMixin, Immutable):
    claim = models.ForeignKey("event_reimbursements.ReimbursementClaim", on_delete=models.CASCADE, related_name="reviews")
    revision = models.ForeignKey("event_reimbursements.ClaimRevision", on_delete=models.CASCADE, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField()
    recommendation = models.CharField(max_length=20)
    reason_code = models.CharField(max_length=64)
    note = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("claim", "revision", "reviewer"), name="reimb_screening_unique")]


class ClaimAttendanceAttestation(ScopedPiiModelMixin, Immutable):
    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    claim = models.ForeignKey("event_reimbursements.ReimbursementClaim", on_delete=models.CASCADE, related_name="attestations")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="+")
    owner_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    attendance_revision = models.PositiveBigIntegerField()
    attended_at = models.DateTimeField()
    venue_evidence_refs = models.JSONField(default=list)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reason_code = models.CharField(max_length=64)
    note = models.TextField(blank=True)
    operation_id = models.UUIDField(unique=True)
