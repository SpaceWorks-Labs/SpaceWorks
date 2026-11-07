"""Metered machine sessions (release 2, lane L23; owner decision #158).

A session is one person's use of one machine, timed from Start to Stop. It is created
by the member (scanning the machine's QR), by staff for a member, or by an integrated
device's own job reports. While it is LIVE (`ended_at` empty) only the closing write may
change it; once closed it is history: a Postgres trigger refuses every UPDATE of a closed
row and every DELETE outside the purge fence. Corrections, the assignment of an
unattributed device session and the staff confirmation are separate append-only
`MachineSessionAmendment` rows, never edits.
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class MachineSession(models.Model):
    class Source(models.TextChoices):
        MEMBER_QR = "member_qr", gettext_noop("Member (machine QR)")
        STAFF = "staff", "Staff"
        DEVICE = "device", gettext_noop("Device report")

    class StopReason(models.TextChoices):
        MEMBER = "member", gettext_noop("Stopped by the member")
        STAFF = "staff", gettext_noop("Stopped by staff")
        MAX_LENGTH = "max_length", gettext_noop("Reached the maximum length")
        CHECK_OUT = "check_out", gettext_noop("The member checked out")
        CLOSING = "closing", gettext_noop("The space closed")
        DEVICE = "device", gettext_noop("The machine reported the end")

    #: Stop reasons the sweep sets; such a session is flagged for staff review.
    AUTO_STOP_REASONS = ("max_length", "check_out", "closing")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="machine_sessions")
    machine = models.ForeignKey("machines.Machine", on_delete=models.CASCADE, related_name="sessions")
    # Denormalised so history keeps its type when a machine is re-typed or retired.
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.PROTECT, related_name="+")
    # Null only for a device session nobody could be attributed to (held for staff).
    member = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="machine_sessions")
    source = models.CharField(max_length=12, choices=Source.choices)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    stop_reason = models.CharField(max_length=12, choices=StopReason.choices, blank=True)
    flagged = models.BooleanField(default=False)
    duration_minutes = models.PositiveIntegerField(default=0)
    # The L15 rate frozen at START (#158.4): the price shown is the price used.
    billable = models.BooleanField(default=False)
    quote_snapshot = models.JSONField(default=dict, blank=True)
    quote_digest = models.CharField(max_length=64, blank=True)
    # A device session that runs an L12 job is billed through that job only.
    service_request = models.ForeignKey("machines.MachineServiceRequest", null=True, blank=True,
                                        on_delete=models.PROTECT, related_name="machine_sessions")
    device_job_ref = models.CharField(max_length=64, blank=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    stopped_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        indexes = [
            models.Index(fields=["makerspace", "started_at"], name="machine_session_space_start"),
            models.Index(fields=["member", "started_at"], name="machine_session_member_start"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["machine"], condition=Q(ended_at__isnull=True),
                                    name="machine_session_one_live_per_machine"),
            models.UniqueConstraint(fields=["member", "machine"], condition=Q(ended_at__isnull=True),
                                    name="machine_session_one_live_per_member_machine"),
            models.UniqueConstraint(fields=["service_request"],
                                    condition=Q(source="device", service_request__isnull=False),
                                    name="machine_session_one_device_session_per_job"),
            models.CheckConstraint(condition=Q(ended_at__isnull=True) | Q(ended_at__gte=F("started_at")),
                                   name="machine_session_ends_after_start"),
            models.CheckConstraint(condition=Q(member__isnull=False) | Q(source="device"),
                                   name="machine_session_member_unless_device"),
        ]

    def __str__(self):
        return f"Session {self.pk} on {self.machine_id}"

    @property
    def live(self):
        return self.ended_at is None


class MachineSessionAmendment(models.Model):
    """Append-only staff decisions on a closed session (#158.5): never an edit."""

    class Kind(models.TextChoices):
        CORRECT = "correct", gettext_noop("Duration corrected")
        ASSIGN = "assign", gettext_noop("Assigned to a member")
        CONFIRM = "confirm", gettext_noop("Confirmed by staff")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    session = models.ForeignKey(MachineSession, on_delete=models.CASCADE, related_name="amendments")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    minutes = models.PositiveIntegerField(null=True, blank=True)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="+")
    reason = models.CharField(max_length=500, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["session"], condition=Q(kind="confirm"),
                                    name="machine_session_one_confirm"),
            models.CheckConstraint(condition=~Q(kind="correct") | Q(minutes__isnull=False),
                                   name="machine_session_correct_has_minutes"),
            models.CheckConstraint(condition=~Q(kind="assign") | Q(member__isnull=False),
                                   name="machine_session_assign_has_member"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise RuntimeError("Machine session amendments are append-only.")
        return super().save(*args, **kwargs)
