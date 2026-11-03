"""Event ID cards (SPEC §4.4), switched by `events.id_cards` (#128, #132).

One live card per confirmed registration, issued automatically once the event has a
published card design (Q-I8), valid until the event's end + 1 day (Q-I6). The name
and photo are scoped PII; the private revocation reason is encrypted. Never charged.
Named `EventIdCard` because `profile_photos` already owns `EventMemberCard`.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin


class EventIdCard(ScopedPiiModelMixin, models.Model):
    class Role(models.TextChoices):
        ATTENDEE = "attendee", "Attendee"
        SPEAKER = "speaker", "Speaker"
        MENTOR = "mentor", "Mentor"
        JUDGE = "judge", "Judge"
        VOLUNTEER = "volunteer", "Volunteer"
        CREW = "crew", "Crew"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REVOKED = "revoked", "Revoked"

    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="id_cards")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, related_name="id_cards")
    person = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="event_id_cards")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.ATTENDEE)
    printed_name = models.TextField(blank=True, default="")
    photo_object_key = models.CharField(max_length=300, blank=True, default="")
    photo_content_type = models.CharField(max_length=64, blank=True, default="")
    photo_size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    photo_consent_at = models.DateTimeField(null=True, blank=True)
    photo_consent_version = models.CharField(max_length=32, blank=True, default="")
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ACTIVE)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.TextField(blank=True, default="")
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    valid_until = models.DateTimeField()
    issued_at = models.DateTimeField(auto_now_add=True)
    last_emailed_at = models.DateTimeField(null=True, blank=True)
    verify_show_name = models.BooleanField(default=False)
    verify_show_photo = models.BooleanField(default=False)
    verify_consent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_id", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["registration"], condition=Q(status="active"),
                                    name="uniq_live_event_id_card"),
            models.CheckConstraint(name="event_id_card_revoked_fields", condition=(
                Q(status="active", revoked_at__isnull=True) | Q(status="revoked", revoked_at__isnull=False))),
        ]
        indexes = [models.Index(fields=["event", "status"], name="eventidcard_event_status_idx")]

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE


class EventCardSettings(models.Model):
    """Per-event card switches. `extras_visible_to_organizers` is the Q-I5 first-aid
    exception: off by default; when on, the event's organisers may read the opt-in blood
    group and emergency contact of THIS event's card holders (every read audited)."""
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="card_settings")
    extras_visible_to_organizers = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
