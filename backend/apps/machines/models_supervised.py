"""Supervised machine sessions at workshops (release 0.12.0, decision 223 (d)/(k)).

A certified instructor opens one ``SupervisedSession`` on a machine (optionally for an
event) and adds supervisees. A supervisee may use the machine only while the session is
open, and each use is a ``SupervisedUse`` recorded under the instructor. Closing a session
is the only edit it ever takes; participants are removed by timestamp, never deleted.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class SupervisedSession(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    machine = models.ForeignKey("machines.Machine", on_delete=models.CASCADE, related_name="supervised_sessions")
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="supervised_sessions_led")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    note = models.CharField(max_length=300, blank=True)
    opened_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-opened_at", "-id"]
        indexes = [models.Index(fields=["makerspace", "opened_at"], name="supsession_space_open_idx")]
        constraints = [
            models.UniqueConstraint(fields=["machine"], condition=Q(closed_at__isnull=True),
                                    name="supervised_session_one_open_per_machine"),
            models.CheckConstraint(condition=Q(closed_at__isnull=True) | Q(closed_at__gte=F("opened_at")),
                                   name="supervised_session_closes_after_open"),
        ]

    @property
    def is_open(self):
        return self.closed_at is None


class SupervisedParticipant(models.Model):
    session = models.ForeignKey(SupervisedSession, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="supervised_participations")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    added_at = models.DateTimeField()
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["session", "user"], name="supervised_participant_uniq"),
        ]


class SupervisedUse(models.Model):
    """One use of the machine by a supervisee, attributed to the session's instructor."""

    session = models.ForeignKey(SupervisedSession, on_delete=models.CASCADE, related_name="uses")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="supervised_uses")
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="supervised_uses_recorded")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["started_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                                   name="supervised_use_ends_after_start"),
        ]
