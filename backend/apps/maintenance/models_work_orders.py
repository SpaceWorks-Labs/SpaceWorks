"""Work orders (machines D7, MT3): the ONE repair/maintenance job model.

L16 builds repairs, issue reports and room/item maintenance on this model, so its
subject covers a machine, an inventory product or asset, or a bookable space from the
start. Each subject kind sits behind its parent's switch (#128 C-9): `machines.maintenance`,
`inventory.maintenance`, `bookings.room_maintenance`.

Status moves open -> in_progress -> done | cancelled (on_hold in between). Closing a
machine work order writes the immutable `MaintenanceLog` as its record; nothing here is
ever deleted outside a tenant purge.
"""

from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q


class WorkOrder(models.Model):
    class Subject(models.TextChoices):
        MACHINE = "machine", "Machine"
        PRODUCT = "inventory_product", gettext_noop("Inventory item")
        ASSET = "inventory_asset", gettext_noop("Inventory unit")
        SPACE = "bookable_space", gettext_noop("Bookable space")

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", gettext_noop("In progress")
        ON_HOLD = "on_hold", gettext_noop("On hold")
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    OPEN_STATUSES = (Status.OPEN, Status.IN_PROGRESS, Status.ON_HOLD)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="work_orders")
    subject_type = models.CharField(max_length=24, choices=Subject.choices)
    machine = models.ForeignKey("machines.Machine", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="work_orders")
    product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="work_orders")
    asset = models.ForeignKey("inventory.InventoryAsset", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="work_orders")
    space = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="work_orders")
    schedule = models.ForeignKey("maintenance.MaintenanceSchedule", null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="work_orders")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    # Starting it takes the machine out of service (and closing puts it back).
    takes_machine_down = models.BooleanField(default=False)
    due_on = models.DateField(null=True, blank=True)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    resolution = models.TextField(blank=True)
    log = models.ForeignKey("maintenance.MaintenanceLog", null=True, blank=True, on_delete=models.SET_NULL,
                            related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    closed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["makerspace", "status", "-created_at"], name="work_order_scope_idx")]
        constraints = [
            models.CheckConstraint(name="work_order_one_subject", condition=(
                Q(subject_type="machine", machine__isnull=False, product__isnull=True, asset__isnull=True,
                  space__isnull=True)
                | Q(subject_type="inventory_product", machine__isnull=True, product__isnull=False,
                    asset__isnull=True, space__isnull=True)
                | Q(subject_type="inventory_asset", machine__isnull=True, product__isnull=True,
                    asset__isnull=False, space__isnull=True)
                | Q(subject_type="bookable_space", machine__isnull=True, product__isnull=True,
                    asset__isnull=True, space__isnull=False))),
        ]

    @property
    def subject(self):
        return self.machine or self.product or self.asset or self.space

    def __str__(self):
        return f"Work order {self.pk}: {self.title}"
