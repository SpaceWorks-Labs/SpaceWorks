"""Durable assignment coverage and private attention preferences."""
from django.conf import settings
from django.db import models
from apps.events.contributions.models_base import AppendOnly, EventBound


class MentorAssignmentRun(AppendOnly, EventBound):
    run_id = models.UUIDField()
    mode = models.CharField(max_length=16)
    decisions = models.JSONField(default=list)
    unsatisfied_team_ids = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["event", "created_by", "run_id"], name="mentor_assignment_actor_run")]


class MentorAttentionPreference(EventBound):
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    muted_until = models.DateTimeField(null=True, blank=True)

    class Meta(EventBound.Meta):
        constraints = [models.UniqueConstraint(fields=["event", "member"], name="mentor_attention_member")]
