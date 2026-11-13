"""Core eligibility is durable, so settlement never imports Events runtime."""

from uuid import uuid4
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .model_base import Immutable


class PayoutEligibility(Immutable):
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE, related_name="eligibility_history")
    evidence_revision = models.PositiveBigIntegerField()
    evidence = models.JSONField(default=dict)
    status = models.CharField(max_length=24, choices=[(v, v) for v in ("eligible", "held", "needs_acknowledgement")])
    reason_code = models.CharField(max_length=64)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    acknowledged_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "payments"
        constraints = [models.UniqueConstraint(fields=("obligation", "evidence_revision"), name="payout_eligibility_revision")]


class PayoutHold(ScopedPiiModelMixin, Immutable):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    obligation = models.ForeignKey("payments.EventPayoutObligation", on_delete=models.CASCADE, related_name="hold_history")
    eligibility_revision = models.PositiveBigIntegerField()
    kind = models.CharField(max_length=12, choices=[(v, v) for v in ("eligibility", "retention")])
    action = models.CharField(max_length=8, choices=[("hold", "hold"), ("release", "release")])
    releases = models.OneToOneField("self", on_delete=models.CASCADE, null=True, related_name="released_by_entry")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    reason_code = models.CharField(max_length=64)
    note = models.TextField(blank=True)
    evidence_refs = models.JSONField(default=list)
    hold_until = models.DateTimeField(null=True)
    operation_id = models.UUIDField(unique=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        app_label = "payments"
        constraints = [models.CheckConstraint(condition=(models.Q(action="hold", releases__isnull=True)
            | models.Q(action="release", releases__isnull=False)), name="payout_hold_release_shape")]
