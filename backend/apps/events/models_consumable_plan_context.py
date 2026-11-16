"""Event-owned optional association for a core consumable plan."""
from django.db import models


class EventConsumablePlanContext(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    plan = models.OneToOneField("inventory.EquipmentConsumablePlan", on_delete=models.PROTECT)
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.PROTECT)
    participant_registration = models.ForeignKey(
        "events.EventRegistration", null=True, blank=True, on_delete=models.PROTECT,
    )
    active = models.BooleanField(default=True)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
