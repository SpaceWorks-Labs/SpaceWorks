"""Ordinary shortlist is a checklist milestone, never an admission writer."""

from django.conf import settings
from django.db import models


class EventStageMilestone(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="stage_milestones")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, null=True, related_name="+")
    application = models.ForeignKey("events.HackathonApplication", on_delete=models.CASCADE, null=True, related_name="+")
    member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stage_milestones")
    kind = models.CharField(max_length=16, default="shortlisted", choices=[("shortlisted", "shortlisted")])
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    published_at = models.DateTimeField()
    withdrawn_at = models.DateTimeField(null=True)
    version = models.PositiveBigIntegerField(default=1)

    class Meta:
        app_label = "events"
        constraints = [
            models.CheckConstraint(condition=(models.Q(registration__isnull=False, application__isnull=True)
                | models.Q(registration__isnull=True, application__isnull=False)), name="stage_milestone_one_subject"),
            models.UniqueConstraint(fields=("event", "member", "kind"), condition=models.Q(withdrawn_at__isnull=True),
                                    name="stage_milestone_active_unique"),
        ]
