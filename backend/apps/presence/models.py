from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from uuid import uuid4

from apps.makerspaces.models import Makerspace, MakerspaceMembership


class PresenceSession(models.Model):
    """Time-boxed current presence; coordinates are deliberately never persisted.

    Creation and ending belong to ``apps.presence.services``. Direct mutation is
    limited to migrations and the read-only superadmin admin surface.
    """

    class EndReason(models.TextChoices):
        SUPERSEDED = "superseded", "Superseded"
        MEMBERSHIP_REVOKED = "membership_revoked", "Membership revoked"
        CLAIM_REVOKED = "claim_revoked", "Claim revoked"
        USER_ENDED = "user_ended", "User ended"
        EXPIRED = "expired", "Expired"
        STAFF_ENDED = "staff_ended", "Staff ended"

    class Status(models.TextChoices):
        WORKING = "working", "Working"
        VISITING = "visiting", "Visiting"
        ATTENDING_EVENT = "attending_event", "Attending an event"
        GUEST = "guest", "Guest"

    # `member` is the legacy identity used by history/claim readers. Keep it in
    # lockstep with account until those readers can migrate together.
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                               related_name="presence_sessions")
    makerspace = models.ForeignKey(Makerspace, on_delete=models.CASCADE)
    membership = models.ForeignKey(MakerspaceMembership, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.VISITING)
    project = models.ForeignKey("makerspaces.MemberProject", on_delete=models.SET_NULL, null=True, blank=True)
    event_registration = models.OneToOneField("events.EventRegistration", on_delete=models.SET_NULL,
                                             null=True, blank=True, related_name="presence_session")
    hide_on_display = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    expiry_reminded_at = models.DateTimeField(null=True, blank=True)
    created_via_claim_session = models.ForeignKey(
        "accounts.MemberClaimCode",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="presence_sessions",
    )
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ended_presence_sessions",
    )
    end_reason = models.CharField(max_length=24, choices=EndReason.choices, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(account=F("member")), name="presence_account_matches_member"),
            models.CheckConstraint(condition=Q(status__in=["working", "visiting", "attending_event", "guest"]),
                                   name="presence_status_valid"),
            models.CheckConstraint(
                condition=Q(expires_at__gt=F("started_at")),
                name="presence_session_expires_after_start",
            )
        ]
        indexes = [
            models.Index(fields=["makerspace", "expires_at"]),
            models.Index(fields=["member", "makerspace", "expires_at"]),
        ]

    def clean(self):
        if self.account_id and self.account_id != self.member_id:
            raise ValidationError("Account and legacy member identity must agree.")
        if self.membership_id and self.makerspace_id and (
            self.membership.makerspace_id != self.makerspace_id
            or self.membership.user_id != self.member_id
        ):
            raise ValidationError("Membership must belong to the member and makerspace.")

    def save(self, *args, **kwargs):
        if not self.account_id:
            self.account_id = self.member_id
        if not self.member_id:
            self.member_id = self.account_id
        return super().save(*args, **kwargs)


class PresenceSettings(models.Model):
    makerspace = models.OneToOneField(Makerspace, on_delete=models.CASCADE, related_name="presence_settings")
    show_names = models.BooleanField(default=True)
    allow_personal_opt_out = models.BooleanField(default=True)
    display_version = models.UUIDField(default=uuid4, editable=False)


class PresencePreference(models.Model):
    makerspace = models.ForeignKey(Makerspace, on_delete=models.CASCADE)
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    hide_on_display = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "account"],
                                              name="presence_preference_account_space")]
