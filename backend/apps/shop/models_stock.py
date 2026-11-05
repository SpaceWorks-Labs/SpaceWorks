"""Shop stock history and checkout holds (release 2 L22). Written only by the availability module.

`ShopStockMovement` is append-only: every restock, count, damage, internal use, sale,
return and write-off is one row with its reason, actor and the balance after it, so the
shelf count can always be explained. A variant that draws on an inventory consumable
records its sales here too (with the consumable's own adjustment in the inventory
ledger), so the shop's history is complete either way.

`ShopCheckoutHold` keeps stock aside while a buyer pays online (Q-S4: 15 minutes) or until
a pay-at-desk order is collected (48 hours). Payment turns it into a sale; expiry,
failure or cancellation releases it.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class ShopStockMovement(models.Model):
    class Kind(models.TextChoices):
        RESTOCK = "restock", "Restocked"
        COUNT = "count", "Stock count correction"
        DAMAGE = "damage", "Damaged"
        INTERNAL_USE = "internal_use", "Internal use"
        SALE = "sale", "Sold"
        RETURNED = "returned", "Returned to stock"
        WRITTEN_OFF = "written_off", "Returned and written off"

    ADJUST_KINDS = (Kind.COUNT, Kind.DAMAGE, Kind.INTERNAL_USE)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    variant = models.ForeignKey("shop.ShopVariant", on_delete=models.CASCADE, related_name="movements")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    #: Signed change to the count (0 for a write-off, which never reaches the shelf).
    quantity = models.IntegerField()
    #: The count after this movement: own stock, or the linked consumable's available units.
    balance_after = models.IntegerField()
    reason = models.CharField(max_length=200, blank=True, default="")
    order = models.ForeignKey("shop.ShopOrder", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                              related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["variant", "created_at"], name="shop_movement_variant_idx")]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Stock movements are append-only.")
        return super().save(*args, **kwargs)


class ShopCheckoutHold(models.Model):
    class Reason(models.TextChoices):
        SOLD = "sold", "Sold"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    order = models.ForeignKey("shop.ShopOrder", on_delete=models.CASCADE, related_name="holds")
    variant = models.ForeignKey("shop.ShopVariant", on_delete=models.CASCADE, related_name="holds")
    quantity = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.CharField(max_length=12, choices=Reason.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expires_at", "pk"]
        indexes = [models.Index(fields=["variant", "released_at"], name="shop_hold_live_idx")]
        constraints = [
            models.UniqueConstraint(fields=["order", "variant"], name="shop_hold_one_per_variant"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="shop_hold_positive"),
            models.CheckConstraint(condition=(Q(released_at__isnull=True, release_reason="")
                                              | (Q(released_at__isnull=False) & ~Q(release_reason=""))),
                                   name="shop_hold_release_shape"),
        ]
