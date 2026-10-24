from django.conf import settings
from django.db import models
from .models_base import AppendOnly, EventBound


class EventContributorAdmission(AppendOnly, EventBound):
    assignment = models.OneToOneField("events.EventRoleAssignment", on_delete=models.CASCADE)
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.PROTECT)
    capacity_policy = models.CharField(max_length=32, choices=[(x, x) for x in (
        "event_capacity", "reserved_contributor_capacity")])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
