from django.conf import settings
from django.db import models
from apps.payments.money_model import MoneyDecimalField


class ToBuyItem(models.Model):
    """A per-makerspace "to buy" / shopping-list entry.

    Each item belongs to one of two streams: HARDWARE (added by space/inventory
    managers) or PRINTING (added by print managers). The makerspace admin (Space
    Manager) and the superadmin see both streams; a print manager sees only the
    printing stream. The stream (`kind`) is decided server-side from the actor's
    role, never trusted from the client (except a makerspace admin / superadmin
    may target either stream)."""

    class Kind(models.TextChoices):
        HARDWARE = "hardware", "Hardware"
        PRINTING = "printing", "Printing"

    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        ORDERED = "ordered", "Ordered"
        RECEIVED = "received", "Received"
        CANCELLED = "cancelled", "Cancelled"

    makerspace = models.ForeignKey(
        "makerspaces.Makerspace",
        on_delete=models.CASCADE,
        related_name="to_buy_items",
    )
    machine_type = models.ForeignKey(
        "machines.MachineType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="to_buy_items",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    link = models.URLField(blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.REQUESTED,
    )
    estimated_unit_cost = MoneyDecimalField(
        max_digits=11,
        decimal_places=3,
        null=True,
        blank=True,
    )
    vendor_name = models.CharField(max_length=200, blank=True)
    actual_unit_cost = MoneyDecimalField(
        max_digits=11,
        decimal_places=3,
        null=True,
        blank=True,
    )
    purchaser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    ordered_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    moved_to_inventory_at = models.DateTimeField(null=True, blank=True)
    resulting_product = models.ForeignKey(
        "inventory.InventoryProduct",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    resulting_pool = models.ForeignKey(
        "machines.MachineConsumablePool",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    resulting_machine = models.ForeignKey(
        "machines.Machine",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    source_pool = models.ForeignKey(
        "machines.MachineConsumablePool",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="low_stock_to_buy_items",
    )
    source_product = models.ForeignKey(
        "inventory.InventoryProduct", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="reorder_drafts",
    )
    # A per-machine grams consumable whose low threshold raised this item; a received
    # item refills that same consumable exactly once (moved_to_inventory_at).
    source_consumable = models.ForeignKey(
        "machines.MachineConsumable", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="low_stock_to_buy_items",
    )
    # Release 2 L22: a shop variant whose reorder point raised this item; marking it bought
    # restocks that variant once, through the availability module (moved_to_inventory_at).
    source_shop_variant = models.ForeignKey(
        "shop.ShopVariant", null=True, blank=True, on_delete=models.SET_NULL, related_name="reorder_drafts",
    )
    # The saved supplier (L12 vendor records); `vendor_name` stays the free-text label.
    vendor = models.ForeignKey(
        "procurement.Vendor", null=True, blank=True, on_delete=models.SET_NULL, related_name="to_buy_items",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["makerspace", "kind", "-created_at"],
                name="proc_tobuy_scope_created_idx",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.kind})"


class ToBuyReceipt(models.Model):
    to_buy_item = models.ForeignKey(
        ToBuyItem,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    object_key = models.CharField(max_length=512, unique=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Receipt for {self.to_buy_item}"


from .models_vendors import Vendor  # noqa: E402,F401
