from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.encryption.mappers import ScopedPiiModelMixin
from apps.events.contributions.models_base import AppendOnly, EventBound


class MentorRound(EventBound):
    index = models.PositiveIntegerField()
    key = models.SlugField(max_length=40)
    label = models.CharField(max_length=100)
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()
    state = models.CharField(max_length=8, default="draft", choices=[
        (x, x) for x in ("draft", "live", "closed", "skipped")])
    form_schema_version = models.PositiveIntegerField(default=1)
    form_schema = models.JSONField(default=dict, blank=True)
    note_keys = models.JSONField(default=list, blank=True)
    rating_keys = models.JSONField(default=list, blank=True)
    help_trigger_rules = models.JSONField(default=list, blank=True)
    allow_fresh_eyes_override = models.BooleanField(default=False)
    allow_conflict_override = models.BooleanField(default=False)
    practice_run_id = models.UUIDField(null=True, blank=True)

    class Meta(EventBound.Meta):
        constraints = [
            models.UniqueConstraint(fields=["event", "key"], name="mentor_round_event_key"),
            models.UniqueConstraint(fields=["event"], condition=Q(state="live", practice_run_id__isnull=True),
                                    name="mentor_one_live_round"),
            models.UniqueConstraint(fields=["event", "practice_run_id"],
                condition=Q(state="live", practice_run_id__isnull=False), name="mentor_one_live_practice_round"),
            models.CheckConstraint(condition=Q(closes_at__gt=models.F("opens_at")), name="mentor_round_window"),
        ]


class MentorRoundLock(ScopedPiiModelMixin, EventBound):
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.CASCADE)
    round = models.ForeignKey(MentorRound, on_delete=models.CASCADE)
    mentor = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT)
    lease_uuid = models.UUIDField()
    generation = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    heartbeat_at = models.DateTimeField()
    started_at = models.DateTimeField()
    overrides = models.TextField(blank=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["team", "round"], name="mentor_round_team_lease")]


class MentorRoundCheckin(ScopedPiiModelMixin, AppendOnly, EventBound):
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.CASCADE)
    round = models.ForeignKey(MentorRound, on_delete=models.CASCADE)
    mentor = models.ForeignKey("events.EventRoleAssignment", on_delete=models.PROTECT)
    form_snapshot = models.JSONField(default=dict, blank=True)
    answers = models.TextField(default="{}")
    overrides = models.TextField(blank=True)
    started_at = models.DateTimeField()
    submitted_at = models.DateTimeField()
    away = models.BooleanField(default=False)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["team", "round"], name="mentor_round_team_checkin")]


class MentorConflict(ScopedPiiModelMixin, EventBound):
    mentor = models.ForeignKey("events.EventRoleAssignment", on_delete=models.CASCADE)
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.CASCADE)
    kind = models.CharField(max_length=12, choices=[(x, x) for x in ("declared", "affiliation", "mentored")])
    active = models.BooleanField(default=True)
    reason = models.TextField(blank=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["mentor", "team", "kind"],
            condition=Q(active=True), name="mentor_conflict_live_kind")]


class MentorNomination(AppendOnly, EventBound):
    mentor = models.ForeignKey("events.EventRoleAssignment", on_delete=models.CASCADE)
    team = models.ForeignKey("events.HackathonTeam", on_delete=models.CASCADE)
    round = models.ForeignKey(MentorRound, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["mentor", "team", "round"], name="mentor_nomination_unique")]


class MentorImportPreview(ScopedPiiModelMixin, EventBound):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.UUIDField(unique=True)
    mapping_sha256 = models.CharField(max_length=64)
    mapping = models.TextField()
    expires_at = models.DateTimeField()
    committed_at = models.DateTimeField(null=True, blank=True)
    practice_run_id = models.UUIDField(null=True, blank=True)


class MentorNotificationIntent(EventBound):
    """Safe references only; a delivery adapter must reauthorize each recipient."""
    request = models.ForeignKey("events.EventHelpRequest", on_delete=models.CASCADE)
    kind = models.CharField(max_length=24)
    generation = models.PositiveIntegerField()
    available_at = models.DateTimeField()
    delivered_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    claim_uuid = models.UUIDField(null=True, blank=True)
    claim_until = models.DateTimeField(null=True, blank=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["request", "kind", "generation"], name="mentor_notice_generation")]
