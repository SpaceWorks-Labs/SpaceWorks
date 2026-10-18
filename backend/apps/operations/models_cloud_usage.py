"""Sampled usage is distinct from provider capacity and unknown is never zero."""
import uuid

from django.db import models


class CloudUsageSample(models.Model):
    metric = models.CharField(max_length=16, choices=[(v, v) for v in ("database", "objects", "email")])
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, on_delete=models.CASCADE)
    scope = models.CharField(max_length=16, choices=[(v, v) for v in ("deployment", "tenant", "provider_account")])
    used = models.PositiveBigIntegerField(null=True)
    uncertain = models.PositiveBigIntegerField(default=0)
    sampled_at = models.DateTimeField()
    source = models.CharField(max_length=100)
    reason_code = models.CharField(max_length=100, blank=True)
    checkpoint = models.JSONField(default=dict)
    configured_cap = models.PositiveBigIntegerField(null=True)
    cap_source = models.CharField(max_length=200, blank=True)
    cap_verified_on = models.DateField(null=True)

    class Meta:
        indexes = [models.Index(fields=["metric", "scope", "makerspace", "-sampled_at"], name="cloud_usage_latest")]


class CloudObjectUsageReceipt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation_key = models.CharField(max_length=128, unique=True)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, on_delete=models.CASCADE)
    bucket_alias = models.CharField(max_length=100)
    object_key_digest = models.CharField(max_length=64)
    generation = models.CharField(max_length=100)
    bytes = models.PositiveBigIntegerField()
    operation = models.CharField(max_length=16, choices=[("finalize", "finalize"), ("delete_confirmed", "delete_confirmed")])
    created_at = models.DateTimeField(auto_now_add=True)
