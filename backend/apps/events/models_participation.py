"""Per-event participation switches and attendance confirmation (lane L21a, X43, #128 C-35).

`EventParticipationSettings` holds the per-event switches this lane adds, every one off by
default: the `stage_advanced` email, "free the place on No", and the crew sign-up and public
crew section. Attendance confirmation is sent by staff only (never automatically): each send
is an `EventAttendanceRound`, at most one every 12 hours per event, and each registered
person's answer is one `EventAttendanceReply` with an optional private note.
"""
from django.utils.translation import gettext_lazy
from django.conf import settings
from django.db import models

from apps.encryption.mappers import ScopedPiiModelMixin


class EventParticipationSettings(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE, related_name="participation_settings")
    stage_advanced_email = models.BooleanField(default=False)
    attendance_free_on_no = models.BooleanField(default=False)
    crew_signup_open = models.BooleanField(default=False)
    crew_approval_required = models.BooleanField(default=True)
    crew_public_section = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def for_event(cls, event):
        row = cls.objects.filter(event=event).first()
        return row or cls(event=event, makerspace_id=event.makerspace_id)


class EventAttendanceRound(models.Model):
    class Kind(models.TextChoices):
        CONFIRMATION = "confirmation", "Confirmation"
        REMINDER = "reminder", "Reminder"

    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="attendance_rounds")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    state = models.CharField(max_length=8, choices=State.choices, default=State.QUEUED)
    recipients = models.PositiveIntegerField(default=0)
    sent = models.PositiveIntegerField(default=0)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["event_id", "-created_at", "-pk"]


class EventAttendanceReply(ScopedPiiModelMixin, models.Model):
    class Answer(models.TextChoices):
        YES = "yes", gettext_lazy("Still coming")
        NO = "no", gettext_lazy("Not coming")

    class Effect(models.TextChoices):
        NONE = "none", gettext_lazy("No change")
        RELEASED = "released", gettext_lazy("Place released")
        DUE_CASE = "due_case", gettext_lazy("Cancelled; refund assessed under policy")
        LEFT_TO_STAFF = "left_to_staff", gettext_lazy("Left to staff")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="attendance_replies")
    registration = models.OneToOneField("events.EventRegistration", on_delete=models.CASCADE,
                                        related_name="attendance_reply")
    asked_at = models.DateTimeField()
    answer = models.CharField(max_length=4, choices=Answer.choices, blank=True, default="")
    note = models.TextField(blank=True, default="")
    replied_at = models.DateTimeField(null=True, blank=True)
    effect = models.CharField(max_length=16, choices=Effect.choices, default=Effect.NONE)
    reminded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["event_id", "pk"]
