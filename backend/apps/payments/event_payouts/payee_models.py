"""Per-obligation routing details. No Saved-details copy or plaintext suffix."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Immutable, RequiredPii


class EventPayeeRevision(RequiredPii, models.Model):
    mandatory_pii_fields = ("details",)
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE, related_name="payee_revisions")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    country = models.CharField(max_length=2)
    template_key = models.CharField(max_length=24)
    template_version = models.PositiveIntegerField()
    method = models.CharField(max_length=16)
    details = models.TextField()  # mandatory encrypted canonical JSON, never a searchable JSONField
    state = models.CharField(max_length=12, default="current", choices=[(v, v) for v in ("current", "superseded", "purged")])
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField()
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    verified_at = models.DateTimeField(null=True)
    paid_closed_at = models.DateTimeField(null=True)
    terminal_financial_at = models.DateTimeField(null=True)
    closure_reason_code = models.CharField(max_length=64, blank=True)
    purge_due_at = models.DateTimeField(null=True)
    purged_at = models.DateTimeField(null=True)
    disclosure_version = models.PositiveIntegerField()

    class Meta:
        app_label = "payments"
        constraints = [
            models.UniqueConstraint(fields=("obligation",), condition=models.Q(state="current"), name="payout_payee_one_current"),
            models.CheckConstraint(condition=(~models.Q(state="purged")
                | models.Q(details="", purged_at__isnull=False)), name="payout_payee_purged_empty"),
        ]


class EventPayeeReview(ScopedPiiModelMixin, Immutable):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE, related_name="payee_reviews")
    payee_revision = models.ForeignKey(EventPayeeRevision, on_delete=models.CASCADE, related_name="reviews")
    sequence = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=20, choices=[(v, v) for v in ("verified", "correction_requested")])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reason_code = models.CharField(max_length=64)
    note = models.TextField(blank=True)
    operation_id = models.UUIDField(unique=True)

    class Meta:
        app_label = "payments"
        constraints = [models.UniqueConstraint(fields=("payee_revision", "sequence"), name="payout_payee_review_sequence")]
