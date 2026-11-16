"""Permanent bucket identity/history floor, independent of credential rotation."""
from django.db import models


class StorageCapabilityState(models.Model):
    identity_fingerprint = models.CharField(max_length=64, unique=True)
    identity = models.JSONField()
    logical_role = models.CharField(max_length=128, null=True, unique=True)
    generation = models.PositiveIntegerField(default=1)
    configuration_fingerprint = models.CharField(max_length=64)
    history_possible = models.BooleanField(default=False)
    facts = models.JSONField(default=dict)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(generation__gte=1, generation__lte=2147483647),
            name="storage_capability_generation_valid",
        )]
