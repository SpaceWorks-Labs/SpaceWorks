"""Apple and Google Wallet passes for a holder card (#132, Q-I11: platform credentials).

The pass authentication token is derived (HMAC) from the serial and never stored; only
its digest is, for constant-time checks on the Apple pass web service. Push tokens are
encrypted at rest. Neither is ever part of a self-export or a tenant-wide report.
"""
from django.db import models
from django.db.models import Q

from .models_holders import HolderCardMixin, exactly_one_holder


class WalletPass(HolderCardMixin):
    class Platform(models.TextChoices):
        APPLE = "apple", "Apple Wallet"
        GOOGLE = "google", "Google Wallet"

    platform = models.CharField(max_length=8, choices=Platform.choices)
    serial = models.CharField(max_length=64, unique=True)
    auth_token_digest = models.CharField(max_length=64)
    pass_type_id = models.CharField(max_length=120, blank=True, default="")
    # Bumped on every content change; Apple's "passesUpdatedSince" tag reads it.
    generation = models.PositiveIntegerField(default=1)
    # What the pass last showed, so the sweep refreshes it after a renewal or expiry.
    content_digest = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now_add=True)
    voided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            exactly_one_holder("wallet_pass_one_holder"),
            *[models.UniqueConstraint(fields=[field, "platform"], condition=Q(**{f"{field}__isnull": False}),
                                      name=f"uniq_wallet_pass_{field}")
              for field in ("member_card", "programme_card", "event_card")],
        ]


class WalletDeviceRegistration(models.Model):
    """An Apple device that asked to receive updates for one pass."""
    wallet_pass = models.ForeignKey(WalletPass, on_delete=models.CASCADE, related_name="devices")
    device_digest = models.CharField(max_length=64)
    push_token = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["wallet_pass", "device_digest"],
                                               name="uniq_wallet_device_registration")]
