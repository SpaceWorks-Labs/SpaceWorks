"""Single-use linked-provider recovery intent; no new identity can be linked."""

from django.conf import settings
from django.db import models


class AccountRestoreIntent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    token_digest = models.CharField(max_length=64, unique=True)
    credential_fingerprint = models.CharField(max_length=64)
    provider = models.CharField(max_length=100)
    nonce_digest = models.CharField(max_length=64)
    origin = models.CharField(max_length=500)
    redirect_uri = models.URLField(max_length=1000)
    pending_secret = models.TextField(blank=True)
    delivery = models.CharField(max_length=16, default="web")
    client_platform = models.CharField(max_length=16, default="web")
    attestation_challenge = models.ForeignKey(
        "accounts.DeviceAttestationChallenge", null=True, on_delete=models.PROTECT,
    )
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
