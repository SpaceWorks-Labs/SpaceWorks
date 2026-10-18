"""Immutable submitted lines preserve amounts, FX and trusted receipt bindings."""

from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Immutable


class ClaimRevision(Immutable):
    claim = models.ForeignKey("event_reimbursements.ReimbursementClaim", on_delete=models.CASCADE, related_name="revisions")
    revision = models.PositiveBigIntegerField()
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    submitted_at = models.DateTimeField()
    currency = models.CharField(max_length=3)
    total_minor = models.PositiveBigIntegerField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=("claim", "revision"), name="reimb_claim_revision_unique")]


class ClaimLine(ScopedPiiModelMixin, Immutable):
    revision = models.ForeignKey(ClaimRevision, on_delete=models.CASCADE, related_name="lines")
    line_uuid = models.UUIDField()
    category = models.CharField(max_length=24)
    vendor = models.TextField()
    description = models.TextField()
    traveller = models.TextField()
    expense_date = models.DateField()
    original_amount_minor = models.PositiveBigIntegerField()
    original_currency = models.CharField(max_length=3)
    fx_rate = models.DecimalField(max_digits=24, decimal_places=12)
    rate_date = models.DateField()
    rate_source = models.CharField(max_length=8, choices=[("manual", "manual"), ("receipt", "receipt")])
    source_note = models.TextField(blank=True)
    converted_minor = models.PositiveBigIntegerField()
    finance_asset = models.ForeignKey("payments.FinanceAttachment", on_delete=models.PROTECT, related_name="claim_lines")
    receipt_hash = models.CharField(max_length=64)
    route = models.TextField(default="{}")
    lodging_starts_on = models.DateField(null=True)
    lodging_ends_on = models.DateField(null=True)
    lodging_nights = models.PositiveSmallIntegerField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("revision", "line_uuid"), name="reimb_claim_line_unique"),
            models.CheckConstraint(condition=models.Q(original_amount_minor__gt=0, fx_rate__gt=0), name="reimb_claim_line_positive"),
        ]
