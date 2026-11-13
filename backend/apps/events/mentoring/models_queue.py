from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from apps.encryption.mappers import ScopedPiiModelMixin
from apps.events.contributions.models_base import AppendOnly, EventBound


class MentorProfile(ScopedPiiModelMixin, EventBound):
    assignment = models.OneToOneField("events.EventRoleAssignment", on_delete=models.CASCADE)
    skills = models.JSONField(default=list, blank=True)
    affiliation = models.TextField(blank=True)
    availability = models.JSONField(default=list, blank=True)
    max_active_teams = models.PositiveSmallIntegerField(default=4)

    class Meta(EventBound.Meta):
        constraints = [models.CheckConstraint(condition=Q(max_active_teams__gte=1, max_active_teams__lte=100),
                                               name="mentor_profile_capacity_bounds")]


class MentorTeamAssignment(EventBound):
    mentor_assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT)
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.CASCADE)
    mode = models.CharField(max_length=16, choices=[
        (x, x) for x in ("manual", "round_robin", "skill_match")])
    state = models.CharField(max_length=8, default="active", choices=[
        (x, x) for x in ("proposed", "active", "ended")])
    active_from = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    run_id = models.UUIDField()

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["mentor_assignment", "team"],
            condition=Q(ended_at__isnull=True), name="mentor_team_live_unique"),
            models.CheckConstraint(condition=(Q(state__in=["proposed", "active"], ended_at__isnull=True)
                | Q(state="ended", ended_at__isnull=False)), name="mentor_assignment_end_shape")]


class EventHelpType(EventBound):
    key = models.SlugField(max_length=40)
    label = models.CharField(max_length=100)
    skill_tags = models.JSONField(default=list, blank=True)
    priority = models.PositiveSmallIntegerField(default=0)
    open_limit = models.PositiveSmallIntegerField(default=1)
    organizer_contact_action = models.CharField(max_length=300, blank=True)
    claim_minutes = models.PositiveSmallIntegerField(default=10)
    expiry_minutes = models.PositiveSmallIntegerField(default=240)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["event", "key"], name="event_help_type_key"),
            models.CheckConstraint(condition=Q(claim_minutes__gte=1, claim_minutes__lte=60,
                expiry_minutes__gte=15, expiry_minutes__lte=10080, open_limit__gte=1, open_limit__lte=10),
                name="help_type_policy_bounds")]


class EventHelpRequest(ScopedPiiModelMixin, EventBound):
    # Null for a drop-in request (#128 C-36, E2-f): an attendee of an event without hackathon
    # teams asks the Mentor Desk on their own; `raised_by` is then the requester.
    team = models.ForeignKey("events.HackathonTeam", null=True, blank=True, on_delete=models.CASCADE)
    type = models.ForeignKey(EventHelpType, on_delete=models.PROTECT)
    raised_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="raised_event_help")
    raised_by_role_assignment = models.ForeignKey("events.EventRoleAssignment", null=True, blank=True,
                                                  on_delete=models.SET_NULL)
    origin = models.CharField(max_length=8, choices=[(x, x) for x in ("team", "mentor", "round", "attendee")])
    structured_zone = models.JSONField(default=dict, blank=True)
    summary = models.TextField()
    state = models.CharField(max_length=10, default="open", choices=[
        (x, x) for x in ("open", "claimed", "resolved", "cancelled", "expired")])
    claimed_by = models.ForeignKey("events.EventRoleAssignment", null=True, blank=True,
                                   on_delete=models.PROTECT, related_name="claimed_help")
    priority = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_opened_at = models.DateTimeField(default=timezone.now)
    open_generation = models.PositiveIntegerField(default=1)
    first_claimed_at = models.DateTimeField(null=True, blank=True)
    last_claimed_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    exclusive_until = models.DateTimeField()
    dedup_key = models.CharField(max_length=64, blank=True)
    practice_run_id = models.UUIDField(null=True, blank=True)
    claim_uuid = models.UUIDField(null=True, blank=True)
    claim_generation = models.PositiveIntegerField(default=0)
    claim_expires_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta(EventBound.Meta):
        constraints = [
            models.UniqueConstraint(fields=["claimed_by"], condition=Q(state="claimed"), name="mentor_one_claimed_help"),
            models.CheckConstraint(condition=Q(team__isnull=False) | Q(origin="attendee"), name="event_help_team_or_drop_in"),
            models.CheckConstraint(condition=(Q(state="claimed", claimed_by__isnull=False)
                | (~Q(state="claimed") & Q(claimed_by__isnull=True))), name="event_help_claim_shape"),
            models.CheckConstraint(condition=(Q(state="claimed", claim_uuid__isnull=False,
                claim_expires_at__isnull=False, claim_generation__gte=1)
                | (~Q(state="claimed") & Q(claim_uuid__isnull=True, claim_expires_at__isnull=True))),
                name="event_help_lease_shape"),
        ]
        indexes = [models.Index(fields=["event", "state", "priority", "created_at"], name="event_help_queue_idx")]


class EventHelpAction(ScopedPiiModelMixin, AppendOnly, EventBound):
    request = models.ForeignKey(EventHelpRequest, on_delete=models.CASCADE, related_name="actions")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=16)
    note = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EventHelpComment(ScopedPiiModelMixin, AppendOnly, EventBound):
    request = models.ForeignKey(EventHelpRequest, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    origin = models.CharField(max_length=8, choices=[(x, x) for x in ("team", "mentor")])
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class OfficeHoursBooking(EventBound):
    slot = models.ForeignKey("events.EventShift", on_delete=models.PROTECT, related_name="bookings")
    # Null for a drop-in booking by one attendee (#128 C-36, E2-f); `booked_by` is then the booker.
    team = models.ForeignKey("events.HackathonTeam", null=True, blank=True, on_delete=models.CASCADE)
    booked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    mentor_assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT)
    state = models.CharField(max_length=10, default="booked", choices=[(x, x) for x in ("booked", "cancelled")])
    operation_uuid = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["slot", "team"],
            condition=Q(state="booked"), name="office_hours_live_team_slot"),
            models.UniqueConstraint(fields=["slot", "booked_by"], condition=Q(state="booked", team__isnull=True),
                                    name="office_hours_live_drop_in_slot")]


class OfficeHoursChange(ScopedPiiModelMixin, AppendOnly, EventBound):
    slot = models.ForeignKey("events.EventShift", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reason = models.TextField()
    old_schedule = models.JSONField(default=dict, blank=True)
    new_schedule = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
