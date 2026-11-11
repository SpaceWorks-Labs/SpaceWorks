"""Append-only measured facts. Actor attribution remains in the audit ledger."""

from django.db import models
from django.db.models import Q


class TrackingQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError("Tracking facts are append-only.")

    def delete(self):
        raise RuntimeError("Tracking facts are append-only.")


class TrackingFact(models.Model):
    objects = TrackingQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Tracking facts are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Tracking facts are append-only.")


class MachineStatusEvent(TrackingFact):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    machine = models.ForeignKey("machines.Machine", on_delete=models.CASCADE, related_name="status_events")
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=32)

    class Meta:
        indexes = [models.Index(fields=["machine", "at"], name="machine_status_timeline_idx")]


#: Shop sources key on the `shop.ShopStockMovement` that moved a linked inventory consumable:
#: `shop_sale` prices a sale, `shop_return` REVERSES part of one (a restock) at the sale's own
#: frozen price, so a report nets it (subtracts) rather than adding it (decision 216 item 11).
SHOP_COST_REVERSAL_KINDS = frozenset({"shop_return"})


class ConsumableCostRecord(TrackingFact):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    source_kind = models.CharField(max_length=32, choices=[(s, s) for s in (
        "pooled_service", "manual_adjustment", "non_pool_consumption", "shop_sale", "shop_return",
    )])
    source_id = models.PositiveBigIntegerField()
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    measurement_unit = models.CharField(max_length=16)
    unit_price_minor_per_measurement_unit = models.DecimalField(max_digits=24, decimal_places=10)
    cost_total_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "source_kind", "source_id"], name="unique_consumable_cost_source"),
            models.CheckConstraint(condition=Q(quantity__gte=0) & Q(unit_price_minor_per_measurement_unit__gte=0), name="consumable_cost_nonnegative"),
        ]
