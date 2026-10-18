"""Trusted tenant/hash parents and immutable receipt allocation evidence."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Immutable


class ReceiptUse(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="receipt_uses")
    sha256 = models.CharField(max_length=64)
    original_currency = models.CharField(max_length=3)
    declared_total_minor = models.PositiveBigIntegerField()
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        app_label = "payments"
        constraints = [models.UniqueConstraint(fields=("makerspace", "sha256"), name="receipt_use_unique_hash")]


class ReceiptAllocationOverride(ScopedPiiModelMixin, Immutable):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    receipt_use = models.ForeignKey(ReceiptUse, on_delete=models.CASCADE, related_name="overrides")
    use_version = models.PositiveBigIntegerField()
    operation_id = models.UUIDField(unique=True)
    allocation_snapshot = models.JSONField()
    total_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reason_code = models.CharField(max_length=64)
    note = models.TextField(blank=True)

    class Meta:
        app_label = "payments"


class ReceiptAllocation(Immutable):
    receipt_use = models.ForeignKey(ReceiptUse, on_delete=models.CASCADE, related_name="allocations")
    use_version = models.PositiveBigIntegerField()
    claim_uuid = models.UUIDField()
    line_uuid = models.UUIDField()
    amount_minor = models.PositiveBigIntegerField()
    override = models.ForeignKey(ReceiptAllocationOverride, on_delete=models.CASCADE, null=True, related_name="allocations")

    class Meta:
        app_label = "payments"
        constraints = [
            models.UniqueConstraint(fields=("receipt_use", "use_version", "claim_uuid", "line_uuid"), name="receipt_allocation_unique"),
            models.CheckConstraint(condition=models.Q(amount_minor__gt=0), name="receipt_allocation_positive"),
        ]
