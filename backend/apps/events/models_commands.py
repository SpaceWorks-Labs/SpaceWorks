"""Replay references contain identifiers only; credentials and answers never enter them."""
from django.conf import settings
from django.db import models


class EventCommandReceipt(models.Model):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    operation_uuid = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    response_reference = models.JSONField(default=dict, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("event", "actor", "operation_uuid"),
                                               name="event_command_operation_unique")]
