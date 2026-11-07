"""Superadmin space controls (owner decision #185).

``SpaceControlState`` is the one row per space holding why and since when it is
suspended or read-only, and its scheduled archive/purge. The hot-path truth stays on
the makerspace (``lifecycle_state == suspended``) and on ``read_only_at`` here; only
``apps.space_controls`` services write either. Announcements are platform rows that
target spaces through ``PlatformAnnouncementTarget``.

None of these rows is tenant data: they are platform governance, omitted from tenant
exports and dumps, and a tenant purge cascades the per-space rows away.
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

DEFAULT_PURGE_GRACE_DAYS = 90


class SpaceControlState(models.Model):
    class ReadOnlySource(models.TextChoices):
        MANUAL = "manual", gettext_noop("Set by the platform operator")
        TRIAL_EXPIRED = "trial_expired", gettext_noop("Trial ended")
        PAYMENT_OVERDUE = "payment_overdue", gettext_noop("Hosting payment overdue")

    makerspace = models.OneToOneField(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="control_state",
    )
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.CharField(max_length=500, blank=True)
    suspended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    read_only_at = models.DateTimeField(null=True, blank=True, db_index=True)
    read_only_reason = models.CharField(max_length=500, blank=True)
    read_only_source = models.CharField(max_length=24, choices=ReadOnlySource.choices, blank=True)
    read_only_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    # Scheduled archive (active space) and/or the purge due after the grace period.
    archive_on = models.DateTimeField(null=True, blank=True, db_index=True)
    purge_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    purge_grace_days = models.PositiveSmallIntegerField(
        default=DEFAULT_PURGE_GRACE_DAYS, validators=[MinValueValidator(1), MaxValueValidator(3650)],
    )
    schedule_note = models.CharField(max_length=500, blank=True)
    scheduled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    # Reminder keys already mailed for the current schedule, e.g. "purge:30".
    reminders_sent = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(suspended_at__isnull=True) | ~Q(suspension_reason=""),
                name="space_control_suspension_has_reason",
            ),
            models.CheckConstraint(
                condition=Q(read_only_at__isnull=True) | ~Q(read_only_source=""),
                name="space_control_read_only_has_source",
            ),
            models.CheckConstraint(
                condition=Q(purge_grace_days__gte=1, purge_grace_days__lte=3650),
                name="space_control_grace_range",
            ),
        ]

    def __str__(self):
        return f"Controls for makerspace {self.makerspace_id}"

    @property
    def has_schedule(self):
        return self.archive_on is not None or self.purge_due_at is not None


class PlatformAnnouncement(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Information"
        MAINTENANCE = "maintenance", "Maintenance"
        POLICY = "policy", "Policy"
        WARNING = "warning", "Warning"

    class Audience(models.TextChoices):
        ALL_SPACES = "all_spaces", gettext_noop("All spaces")
        SELECTED_SPACES = "selected_spaces", gettext_noop("Selected spaces")

    title = models.CharField(max_length=120)
    body = models.TextField(max_length=4000)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.INFO)
    audience = models.CharField(max_length=16, choices=Audience.choices, default=Audience.ALL_SPACES)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    send_email = models.BooleanField(default=False)
    show_to_members = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_recipient_count = models.PositiveIntegerField(default=0)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-starts_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")),
                name="platform_announcement_ends_after_start",
            ),
        ]

    def __str__(self):
        return self.title


class PlatformAnnouncementTarget(models.Model):
    """One targeted space of a ``selected_spaces`` announcement."""

    announcement = models.ForeignKey(PlatformAnnouncement, on_delete=models.CASCADE, related_name="targets")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("announcement", "makerspace"), name="uniq_announcement_target"),
        ]
