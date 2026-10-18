"""One canonical, owner-only sponsor résumé consent plus immutable safe history."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from .models_base import AppendOnly, EventOwned


class ParticipantSponsorResumeConsent(EventOwned):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    sponsor = models.ForeignKey("events.EventSponsor", on_delete=models.PROTECT, related_name="+")
    participant_asset = models.ForeignKey("events.HackathonParticipantAsset", on_delete=models.PROTECT, related_name="+")
    asset_sha256 = models.CharField(max_length=64)
    purpose = models.CharField(max_length=16, default="recruiting")
    state = models.CharField(max_length=8, default="revoked", choices=(("granted", "Granted"), ("revoked", "Revoked")))
    consent_revision = models.PositiveIntegerField(default=1)
    disclosure_revision = models.PositiveIntegerField()
    consented_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("event", "member", "sponsor", "participant_asset", "purpose"),
                                    name="ev_resume_consent_identity"),
            models.CheckConstraint(condition=Q(purpose="recruiting"), name="ev_resume_recruiting_only"),
            models.CheckConstraint(condition=Q(state="granted", revoked_at__isnull=True)
                                   | Q(state="revoked", revoked_at__isnull=False), name="ev_resume_consent_state"),
        ]


class SponsorResumeConsentHistory(AppendOnly):
    consent = models.ForeignKey(ParticipantSponsorResumeConsent, on_delete=models.CASCADE, related_name="history")
    revision = models.PositiveIntegerField()
    state = models.CharField(max_length=8)
    asset_sha256 = models.CharField(max_length=64)
    disclosure_revision = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    reason_code = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("consent", "revision"), name="ev_resume_consent_history")]
