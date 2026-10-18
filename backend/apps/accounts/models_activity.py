"""Deployment-local session activity; no token or attestation identity is retained."""

from django.db import models


class DeviceActivityDay(models.Model):
    grant = models.ForeignKey("accounts.DeviceGrant", on_delete=models.CASCADE)
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    platform = models.CharField(max_length=16)
    local_day = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["grant", "makerspace", "local_day"], nulls_distinct=False,
            name="unique_grant_space_activity_day",
        )]


class AttestationVerificationLog(models.Model):
    platform = models.CharField(max_length=16)
    mode = models.CharField(max_length=32)
    outcome = models.CharField(max_length=16, choices=[
        ("sent", "Verified"), ("failed", "Rejected"), ("skipped", "Unavailable"),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
