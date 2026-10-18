"""Private, append-only explanations for exceptional contributor operations."""
from django.conf import settings
from django.db import models
from apps.encryption.mappers import ScopedPiiModelMixin
from .models_base import AppendOnly, EventBound


class EventRoleAnswerRevision(ScopedPiiModelMixin, AppendOnly, EventBound):
    assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.CASCADE,
                                   related_name="answer_revisions")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    answers = models.TextField()
    reason = models.TextField()
    schema_version = models.PositiveIntegerField()
    locked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class EventRequirementOverride(ScopedPiiModelMixin, AppendOnly, EventBound):
    assignment = models.ForeignKey("events.EventRoleAssignment", on_delete=models.CASCADE)
    shift = models.ForeignKey("events.EventShift", null=True, blank=True, on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    kind = models.CharField(max_length=8, choices=[("training", "training"), ("briefing", "briefing")])
    reference_id = models.PositiveIntegerField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
