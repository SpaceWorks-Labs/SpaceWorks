"""Phone verification challenges -- the twin of EmailVerificationChallenge.

Two purposes are carried by one model, discriminated by `purpose`:

* LINK   -- an authenticated user proving they hold a number, to attach it.
* LOGIN  -- an anonymous caller proving they hold an already-verified number.

Keeping them in one table but distinguishing the purpose is deliberate. A LINK
challenge must never be redeemable at the login endpoint: otherwise a member who
starts linking a number and walks away leaves a code that signs someone in.
"""

from django.utils.translation import gettext_lazy
from django.db import models


class PhoneChallengePurpose(models.TextChoices):
    LINK = "link", gettext_lazy("Link a phone number")
    LOGIN = "login", gettext_lazy("Sign in with a phone number")
    REAUTH = "reauth", gettext_lazy("Reauthenticate with a phone number")
    RESTORE = "restore", gettext_lazy("Restore an archived account")


class PhoneVerificationChallenge(models.Model):
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="phone_challenges"
    )
    purpose = models.CharField(max_length=16, choices=PhoneChallengePurpose.choices)
    # NULL is browser delivery. A device OTP names one exact, one-time app proof.
    attestation_challenge = models.ForeignKey(
        "accounts.DeviceAttestationChallenge",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="phone_login_challenges",
    )
    # The E.164 number this challenge was issued against, snapshotted. A later edit to
    # the user's number leaves this row unable to match, which is the intended lapse.
    phone_e164 = models.CharField(max_length=20)
    code_digest = models.CharField(max_length=128)
    credential_fingerprint = models.CharField(max_length=64, blank=True, default="")
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "phone_e164", "expires_at"]),
            models.Index(
                fields=["purpose", "phone_e164"],
                condition=models.Q(consumed_at__isnull=True),
                name="phone_challenge_active_idx",
            ),
        ]

    def is_usable(self, now):
        return (
            self.consumed_at is None
            and self.failed_attempts < 5
            and self.expires_at > now
        )

    def __str__(self):
        return f"{self.purpose} challenge for user {self.user_id}"
