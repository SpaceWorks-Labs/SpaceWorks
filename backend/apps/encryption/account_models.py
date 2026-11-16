"""Account-owned key custody; intentionally independent of tenant encryption."""

from django.conf import settings
from django.db import models
from django.db.models import Q


class AccountPiiKey(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ROTATED = "rotated", "Rotated"
        DISABLED = "disabled", "Disabled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="account_pii_keys")
    version = models.PositiveIntegerField()
    wrapped_dek = models.BinaryField()
    broker_backend = models.CharField(max_length=16)
    broker_key_id = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "version"], name="account_dek_version_unique"),
            models.UniqueConstraint(fields=["user"], condition=Q(status="active"),
                                    name="account_active_dek_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="account_dek_positive"),
        ]


class PiiAccountWriteFence(models.Model):
    """Epoch outlives key revocation so prepared ciphertext cannot resurrect data."""

    class State(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        ERASED = "erased", "Erased"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="account_pii_write_fence")
    state = models.CharField(max_length=8, choices=State.choices, default=State.OPEN)
    epoch = models.PositiveBigIntegerField(default=1)
    claim_id = models.UUIDField(null=True, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    operation_id = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(epoch__gte=1),
                                              name="account_fence_epoch_positive")]
