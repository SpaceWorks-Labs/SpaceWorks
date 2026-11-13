"""Team identities, private coordination, revocable invitation digests."""
from uuid import uuid4
from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.encryption.mappers import ScopedPiiModelMixin


class HackathonTeam(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="hackathon_teams")
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100)
    leader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="led_hackathon_teams")
    state = models.CharField(max_length=12, default="forming", choices=[(v, v) for v in ("forming", "locked", "disbanded")])
    version = models.PositiveIntegerField(default=1)
    zone = models.CharField(max_length=64, blank=True)
    table = models.CharField(max_length=32, blank=True)
    seeking_members = models.BooleanField(default=False)
    finder_intro = models.CharField(max_length=500, blank=True)
    skills = models.JSONField(default=list)
    public_profile_refs = models.JSONField(default=list)
    roster_hash = models.CharField(max_length=64, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    eligibility_issue = models.BooleanField(default=False)
    roster_reopened_until = models.DateTimeField(null=True, blank=True)
    #: Organiser delete with a short undo (E-B3): when it happened, and who was in the team then.
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_snapshot = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "normalized_name"], condition=~Q(state="disbanded"), name="ha_active_team_name_unique")]


class HackathonTeamMember(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE, related_name="memberships")
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.PROTECT)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="hackathon_team_memberships")
    state = models.CharField(max_length=12, default="requested", choices=[(v, v) for v in ("invited", "requested", "active", "left", "removed", "declined")])
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "member"], condition=Q(state="active"), name="ha_one_active_team_member"),
            models.UniqueConstraint(fields=["team", "member"], condition=Q(state__in=["active", "requested", "invited"]), name="ha_one_live_team_request"),
        ]


class HackathonTeamInvite(models.Model):
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE, related_name="invites")
    token_digest = models.CharField(max_length=64, unique=True)
    email_digest = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class HackathonFinderProfile(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    version = models.PositiveIntegerField(default=1)
    opted_in = models.BooleanField(default=False)
    intro = models.CharField(max_length=500, blank=True)
    skills = models.JSONField(default=list)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "member"], name="ha_finder_event_member_unique")]


class TeamComment(ScopedPiiModelMixin, models.Model):
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    encrypted_body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Team comments are append-only.")
        return super().save(*args, **kwargs)


class HackathonTeamException(models.Model):
    team = models.ForeignKey(HackathonTeam, on_delete=models.CASCADE, related_name="eligibility_exceptions")
    rule = models.CharField(max_length=16, choices=[("team_size", "Team size"), ("attendance", "Attendance")])
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    roster_hash = models.CharField(max_length=64)
    reason_code = models.CharField(max_length=40)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(rule="team_size", member__isnull=True) | Q(rule="attendance", member__isnull=False), name="ha_exception_subject_shape")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Team exceptions are immutable and bound to one roster.")
        return super().save(*args, **kwargs)
