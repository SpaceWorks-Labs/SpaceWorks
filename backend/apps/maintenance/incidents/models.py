"""Incident register rows: safety incidents and near misses, with follow-up actions.

An incident is the *record* that something happened (who, what, where, how serious, what
was done); it is not a repair. A repair stays an `IssueReport` and an incident may point at
one (`repair_issue`). The links to a loan, booking, event, machine, room or repair are all
optional and `SET_NULL`: the register is accountability history and must outlive the row it
mentions. `area` decides who besides the Space Manager may read it (decision 219 (e)).

`guest_pass` and `sponsor_user` carry a guest's incident and the sponsor's side of it
(223 (f)); both are `SET_NULL`, so the record outlives the pass.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_noop

from apps.encryption.mappers import ScopedPiiModelMixin


class Incident(ScopedPiiModelMixin, models.Model):
    class Kind(models.TextChoices):
        INCIDENT = "incident", gettext_noop("Incident")
        NEAR_MISS = "near_miss", gettext_noop("Near miss")

    class Severity(models.TextChoices):
        LOW = "low", gettext_noop("Low")
        MEDIUM = "medium", gettext_noop("Medium")
        HIGH = "high", gettext_noop("High")
        CRITICAL = "critical", gettext_noop("Critical")

    class Status(models.TextChoices):
        REPORTED = "reported", gettext_noop("Reported")
        TRIAGED = "triaged", gettext_noop("Triaged")
        IN_PROGRESS = "in_progress", gettext_noop("In progress")
        RESOLVED = "resolved", gettext_noop("Resolved")
        CLOSED = "closed", gettext_noop("Closed")

    class Area(models.TextChoices):
        MACHINES = "machines", gettext_noop("Machines")
        LENDING = "lending", gettext_noop("Inventory")
        EVENTS = "events", gettext_noop("Events")
        BOOKINGS = "bookings", gettext_noop("Rooms and bookings")
        OTHER = "other", gettext_noop("Other (Space Manager only)")

    OPEN_STATUSES = (Status.REPORTED, Status.TRIAGED, Status.IN_PROGRESS)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="incidents")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.INCIDENT)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.LOW)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REPORTED)
    area = models.CharField(max_length=10, choices=Area.choices, default=Area.OTHER)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=200, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    involved_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Scoped PII (encryption/registry_r2_l16.py): ciphertext outgrows a varchar, so TextField; the 200-char
    # limit is enforced by the serializer.
    involved_note = models.TextField(blank=True)
    sponsor_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    machine = models.ForeignKey(
        "machines.Machine", null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents")
    room = models.ForeignKey(
        "bookings.BookableSpace", null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents")
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    loan = models.ForeignKey(
        "hardware_requests.HardwareRequest", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    booking = models.ForeignKey(
        "bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    repair_issue = models.ForeignKey(
        "maintenance.IssueReport", null=True, blank=True, on_delete=models.SET_NULL, related_name="incidents")
    guest_pass = models.ForeignKey(
        "makerspaces.GuestPass", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    triaged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    resolution_note = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(fields=["makerspace", "status", "occurred_at"], name="incident_space_status_idx"),
            models.Index(fields=["makerspace", "area"], name="incident_space_area_idx"),
        ]

    def __str__(self):
        return f"Incident {self.pk}: {self.title}"


class IncidentAction(models.Model):
    """One follow-up action on an incident (a fix, a briefing, a policy change)."""

    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="actions")
    description = models.CharField(max_length=300)
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    due_date = models.DateField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
