"""Definitions select immutable F form revisions; publishing never edits history."""

from uuid import uuid4
from django.conf import settings
from django.db import models


def reminder_offsets():
    return [-604800, -86400]


def audience():
    return {"roles": [], "track_ids": [], "travel_requested": None}


class EventStageForm(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="stage_forms")
    slug = models.SlugField(max_length=64)
    title = models.CharField(max_length=200)
    stage = models.CharField(max_length=16, choices=[(v, v) for v in (
        "application", "shortlisted", "accepted_rsvp", "pre_event", "post_event")])
    activation_point = models.CharField(max_length=8, blank=True, default="", choices=[("", ""),
        ("accepted", "accepted"), ("rsvp", "rsvp")])
    state = models.CharField(max_length=12, default="draft", choices=[(v, v) for v in ("draft", "published", "retired")])
    version = models.PositiveBigIntegerField(default=1)
    form_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    current_revision = models.ForeignKey("events.EventFormRevision", on_delete=models.PROTECT,
                                        null=True, related_name="+")
    opening_mode = models.CharField(max_length=16, default="trigger")
    opens_at = models.DateTimeField(null=True)
    opening_offset_seconds = models.IntegerField(null=True)
    due_mode = models.CharField(max_length=16, default="after_trigger")
    due_at = models.DateTimeField(null=True)
    due_after_seconds = models.PositiveIntegerField(null=True)
    due_event_offset_seconds = models.IntegerField(null=True)
    reminder_offsets = models.JSONField(default=reminder_offsets)
    required = models.BooleanField(default=False)
    missed_action = models.CharField(max_length=8, default="none", choices=[(v, v) for v in ("none", "warn", "block")])
    blocked_actions = models.JSONField(default=list)
    lock_on_next_stage = models.BooleanField(default=True)
    audience = models.JSONField(default=audience)
    schema_version = models.PositiveSmallIntegerField(default=2)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True)
    retired_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "events"
        constraints = [
            models.UniqueConstraint(fields=("event", "slug"), name="stage_form_unique_slug"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="stage_form_version_positive"),
            models.CheckConstraint(condition=(models.Q(stage="accepted_rsvp", activation_point__in=("accepted", "rsvp"))
                | (~models.Q(stage="accepted_rsvp") & models.Q(activation_point=""))), name="stage_activation_shape"),
            models.CheckConstraint(condition=(models.Q(due_mode="absolute", due_at__isnull=False,
                due_after_seconds__isnull=True, due_event_offset_seconds__isnull=True)
                | models.Q(due_mode="after_trigger", due_at__isnull=True, due_after_seconds__gt=0,
                           due_after_seconds__lte=31536000, due_event_offset_seconds__isnull=True)
                | models.Q(due_mode__in=("event_start", "event_end"), due_at__isnull=True,
                           due_after_seconds__isnull=True, due_event_offset_seconds__gte=-31536000,
                           due_event_offset_seconds__lte=31536000)), name="stage_due_shape"),
            models.CheckConstraint(condition=(models.Q(opening_mode="trigger", opens_at__isnull=True,
                opening_offset_seconds__isnull=True) | models.Q(opening_mode="absolute", opens_at__isnull=False,
                opening_offset_seconds__isnull=True) | models.Q(opening_mode__in=("event_start", "event_end"),
                opens_at__isnull=True, opening_offset_seconds__gte=-31536000,
                opening_offset_seconds__lte=31536000)), name="stage_opening_shape"),
        ]
