"""Claims retain their finance decision state; paid status is a core projection."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Versioned


class ReimbursementClaim(ScopedPiiModelMixin, Versioned):
    uuid = models.UUIDField(default=uuid4, unique=True, editable=False)
    award = models.OneToOneField("event_reimbursements.GrantAward", on_delete=models.CASCADE, related_name="claim")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="reimbursement_claims")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reimbursement_claims")
    state = models.CharField(max_length=20, default="draft", choices=[(v, v) for v in (
        "draft", "open", "submitted", "returned_for_info", "approved", "partially_approved", "rejected",
        "withdrawn", "expired", "under_review")])
    draft_payload = models.TextField(default="{}")
    submitted_at = models.DateTimeField(null=True)
    effective_due_at = models.DateTimeField()
    due_revision = models.PositiveBigIntegerField(default=1)
    extension_reason = models.TextField(blank=True)
    current_revision = models.ForeignKey("event_reimbursements.ClaimRevision", on_delete=models.SET_NULL, null=True, related_name="+")
    current_decision = models.ForeignKey("event_reimbursements.ClaimDecision", on_delete=models.SET_NULL, null=True, related_name="+")
    domain_closed_at = models.DateTimeField(null=True)
    domain_closure_reason_code = models.CharField(max_length=64, blank=True)
    appeal_used = models.BooleanField(default=False)
    info_due_at = models.DateTimeField(null=True)
    appeal_due_at = models.DateTimeField(null=True)


class ReimbursementWorkItem(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="reimbursement_work")
    award = models.ForeignKey("event_reimbursements.GrantAward", on_delete=models.CASCADE, null=True, related_name="work_items")
    claim = models.ForeignKey(ReimbursementClaim, on_delete=models.CASCADE, null=True, related_name="work_items")
    kind = models.CharField(max_length=24)
    due_at = models.DateTimeField(db_index=True)
    state = models.CharField(max_length=12, default="pending")
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(award__isnull=False, claim__isnull=True)
            | models.Q(award__isnull=True, claim__isnull=False)), name="reimb_work_one_subject")]
