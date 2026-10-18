"""Immutable form-definition history, not member answers or saved account details."""

from django.conf import settings
from django.db import models


class EventFormRevision(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="form_revisions")
    form_key = models.CharField(max_length=16, choices=[(key, key) for key in (
        "registration", "application", "volunteer", "mentor", "round", "track")])
    selector_kind = models.CharField(max_length=8, default="none", choices=[(key, key) for key in (
        "none", "posting", "round", "track")])
    selector_id = models.PositiveBigIntegerField(null=True)
    revision = models.PositiveBigIntegerField()
    schema = models.JSONField(null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "events"
        constraints = [
            models.UniqueConstraint(fields=("event", "form_key", "selector_kind", "selector_id", "revision"),
                                    nulls_distinct=False, name="uniq_event_form_revision"),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name="event_form_revision_positive"),
            models.CheckConstraint(condition=(models.Q(selector_id__isnull=True) | models.Q(selector_id__gte=1)),
                                   name="event_form_selector_positive"),
            models.CheckConstraint(condition=(models.Q(selector_kind="none", selector_id__isnull=True)
                | models.Q(selector_kind__in=("posting", "round", "track"), selector_id__isnull=False)),
                name="event_form_selector_consistent"),
            models.CheckConstraint(condition=(models.Q(form_key__in=("registration", "application"), selector_kind="none")
                | models.Q(form_key__in=("volunteer", "mentor"), selector_kind="posting")
                | models.Q(form_key="round", selector_kind="round") | models.Q(form_key="track", selector_kind="track")),
                name="event_form_selector_matches_key"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("EventFormRevision rows are immutable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("EventFormRevision rows are retained until an authorized purge.")
