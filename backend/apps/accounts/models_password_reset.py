"""Single-row queue and challenge state for account recovery."""

from django.db import models


class PasswordResetEnvelopeStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CLAIMED = "claimed", "Claimed"
    DELIVERING = "delivering", "Delivering"
    ISSUED = "issued", "Issued"
    CONSUMED = "consumed", "Consumed"
    DISCARDED = "discarded", "Discarded"
    UNDELIVERABLE = "undeliverable", "Undeliverable"
    DELIVERY_UNKNOWN = "delivery_unknown", "Delivery unknown"


class PasswordResetEnvelope(models.Model):
    """One reusable recovery envelope for each account and its immutable namespace.

    The stable row is both the request queue item and the confirmation lock target.
    Email is a delivery address, never account ownership. Unknown addresses and
    unavailable accounts receive the same public acknowledgement without a queue row.
    """

    purpose = models.CharField(max_length=16, default="reset", choices=[("reset", "Reset"), ("restore", "Restore")])
    email_normalized = models.CharField(max_length=254)
    context = models.CharField(max_length=8, choices=[(kind, kind.title()) for kind in ("member", "staff", "platform")], default="member")
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE)
    request_origin = models.CharField(max_length=512, blank=True)
    credential_generation = models.PositiveBigIntegerField(default=0)
    email_fingerprint = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)
    digest_is_live = models.BooleanField(default=False)
    credential_fingerprint = models.CharField(max_length=64, blank=True)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="password_reset_envelopes",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=PasswordResetEnvelopeStatus.choices,
        default=PasswordResetEnvelopeStatus.PENDING,
    )
    claimed_at = models.DateTimeField(null=True, blank=True)
    claim_owner = models.CharField(max_length=128, blank=True)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    generation = models.PositiveBigIntegerField(default=0)
    requested_at = models.DateTimeField()
    superseded_at = models.DateTimeField(null=True, blank=True)
    terminal_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="uniq_password_reset_account",
            )
        ]
        indexes = [
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["status", "claim_expires_at"]),
            models.Index(fields=["terminal_at"]),
        ]

    def __str__(self):
        return f"Password reset envelope #{self.pk} [{self.status}]"
