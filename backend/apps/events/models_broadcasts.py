"""Event campaign identity and concrete recipient uniqueness."""

from django.db import models
from apps.integrations.broadcasts_models import BroadcastCampaign, BroadcastDelivery


class EventBroadcast(BroadcastCampaign):
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="broadcasts")
    statuses = models.JSONField(default=list)
    attendance = models.CharField(max_length=12, default="any",
                                  choices=[("any", "Any"), ("attended", "Attended"), ("not_attended", "Not attended")])


class EventBroadcastDelivery(BroadcastDelivery):
    campaign = models.ForeignKey(EventBroadcast, on_delete=models.CASCADE, related_name="deliveries")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["campaign", "recipient"], name="uniq_event_broadcast_account")]
