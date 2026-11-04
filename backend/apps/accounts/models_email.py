"""Platform email verification challenges and daily send accounting."""

from django.conf import settings
from django.db import models

class EmailVerificationChallenge(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_challenges"
    )
    email = models.CharField(max_length=254)
    code_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "email", "expires_at"]),
            models.Index(
                fields=["user", "email"],
                condition=models.Q(consumed_at__isnull=True),
                name="email_challenge_active_idx",
            ),
        ]

    def is_usable(self, now):
        return (
            self.consumed_at is None
            and self.failed_attempts < 5
            and self.expires_at > now
        )


class DailyOtpEmailCounter(models.Model):
    day = models.DateField(unique=True)
    count = models.PositiveIntegerField(default=0)


