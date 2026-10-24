"""Ephemeral masked checklist coordination stores IDs/versions, never bank data."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from .model_base import Immutable


class PayoutExportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="payout_export_batches")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    operation_id = models.UUIDField(unique=True)
    command_digest = models.CharField(max_length=64)
    selection_filter = models.JSONField(default=dict)
    selection_hash = models.CharField(max_length=64)
    state = models.CharField(max_length=8, default="ready", choices=[("ready", "ready"), ("expired", "expired")])
    expires_at = models.DateTimeField()
    mask_policy_version = models.PositiveSmallIntegerField(default=1)
    downloaded_at = models.DateTimeField(null=True)
    download_count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "payments"


class PayoutExportBatchItem(Immutable):
    batch = models.ForeignKey(PayoutExportBatch, on_delete=models.CASCADE, related_name="items")
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE, related_name="export_items")
    obligation_version = models.PositiveBigIntegerField()
    payee_revision = models.ForeignKey("payments.EventPayeeRevision", on_delete=models.CASCADE, related_name="export_items")
    payee_version = models.PositiveBigIntegerField()
    remaining_minor = models.PositiveBigIntegerField()

    class Meta:
        app_label = "payments"
        constraints = [models.UniqueConstraint(fields=("batch", "obligation"), name="payout_export_item_unique")]
