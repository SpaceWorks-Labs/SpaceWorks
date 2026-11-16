"""Observations, never reconstructed history: missed days remain gaps."""

from django.db import models

class SnapshotQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError("Stock observations are append-only.")

    def delete(self):
        raise RuntimeError("Stock observations are append-only.")



class InventoryStockSnapshot(models.Model):
    objects = SnapshotQuerySet.as_manager()

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    product = models.ForeignKey("inventory.InventoryProduct", on_delete=models.CASCADE)
    local_day = models.DateField()
    available = models.PositiveIntegerField()
    issued = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    out_of_stock = models.BooleanField()
    below_reorder = models.BooleanField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["product", "local_day"], name="unique_product_stock_day")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Stock observations are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Stock observations are append-only.")
