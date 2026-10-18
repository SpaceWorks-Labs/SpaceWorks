from django.conf import settings
from django.db import models
from django.db.models import F, Q
from apps.encryption.mappers import ScopedPiiModelMixin
from .models_base import AppendOnly, EventBound


class EventShift(EventBound):
    posting = models.ForeignKey("events.EventRolePosting", on_delete=models.PROTECT)
    kind = models.CharField(max_length=12, default="volunteer", choices=[
        (x, x) for x in ("volunteer", "office_hours")])
    mentor_assignment = models.ForeignKey("events.EventRoleAssignment", null=True, blank=True, on_delete=models.PROTECT)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    zone = models.CharField(max_length=100, blank=True)
    task = models.CharField(max_length=200)
    capacity = models.PositiveIntegerField(default=0)
    signup_deadline = models.DateTimeField()
    waitlist_enabled = models.BooleanField(default=True)
    approval_required = models.BooleanField(default=True)
    requirements = models.JSONField(default=dict, blank=True)
    permission_preset = models.JSONField(default=list, blank=True)
    grace_minutes = models.PositiveSmallIntegerField(default=15)
    state = models.CharField(max_length=8, default="open", choices=[(x, x) for x in ("open", "closed")])

    class Meta(EventBound.Meta):
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=F("starts_at")), name="event_shift_window"),
            models.CheckConstraint(condition=Q(signup_deadline__lte=F("starts_at")), name="event_shift_deadline"),
            models.CheckConstraint(condition=Q(grace_minutes__lte=60), name="event_shift_grace_bound"),
            models.CheckConstraint(condition=(Q(kind="volunteer", mentor_assignment__isnull=True)
                | Q(kind="office_hours", mentor_assignment__isnull=False)), name="event_shift_kind_shape"),
        ]


class EventShiftSignup(EventBound):
    shift = models.ForeignKey(EventShift, on_delete=models.CASCADE, related_name="signups")
    assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    state = models.CharField(max_length=12, default="applied", choices=[
        (x, x) for x in ("applied", "waitlisted", "approved", "withdrawn", "declined")])
    queue_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="approved_event_shift_signups")

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["shift", "member"], name="event_shift_member_unique")]


class EventShiftAttendance(EventBound):
    signup = models.OneToOneField(EventShiftSignup, on_delete=models.CASCADE, related_name="attendance")
    state = models.CharField(max_length=12, default="scheduled", choices=[
        (x, x) for x in ("scheduled", "checked_in", "checked_out", "no_show")])
    checked_in_at = models.DateTimeField(null=True, blank=True)
    checked_out_at = models.DateTimeField(null=True, blank=True)
    break_minutes = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=16, default="self")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta(EventBound.Meta):
        constraints = [models.CheckConstraint(condition=(Q(checked_out_at__isnull=True)
            | Q(checked_in_at__isnull=False, checked_out_at__gte=F("checked_in_at"))),
            name="event_shift_attendance_order")]


class EventContributionHours(EventBound):
    signup = models.OneToOneField(EventShiftSignup, on_delete=models.CASCADE, related_name="hours")
    minutes = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=8, default="pending", choices=[
        (x, x) for x in ("pending", "verified", "adjusted")])


class EventContributionHoursEntry(ScopedPiiModelMixin, AppendOnly, EventBound):
    hours = models.ForeignKey(EventContributionHours, on_delete=models.CASCADE, related_name="entries")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    previous_version = models.PositiveIntegerField()
    minutes = models.PositiveIntegerField()
    kind = models.CharField(max_length=8, choices=[(x, x) for x in ("verified", "adjusted")])
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["hours", "previous_version"], name="event_hours_revision_unique")]


class EventShiftAttendanceCorrection(ScopedPiiModelMixin, AppendOnly, EventBound):
    attendance = models.ForeignKey(EventShiftAttendance, on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=12)
    occurred_at = models.DateTimeField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
