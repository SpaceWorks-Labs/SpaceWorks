"""Room outages (#93, #128 C-6b) and maintenance on items and rooms (#128 C-9).

A room out of service either BLOCKS new bookings (the default) or WARNS; one open outage
per room, closed when the room is back. Machines go out of service through their own
status (the downtime ledger), units and items through `inventory/availability.py`.

Machine maintenance keeps L12's machine schedules and logs. `inventory.maintenance` and
`bookings.room_maintenance` add the same idea for an inventory item or unit and for a
bookable room: a recurring schedule and an append-only log of each run.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .models_records import AppendOnly

ITEM_SUBJECTS = [("inventory_product", "Inventory item"), ("inventory_asset", "Inventory unit"),
                 ("bookable_space", "Bookable space")]
_SUBJECT_SHAPE = (
    Q(subject_type="inventory_product", product__isnull=False, asset__isnull=True, room__isnull=True)
    | Q(subject_type="inventory_asset", product__isnull=True, asset__isnull=False, room__isnull=True)
    | Q(subject_type="bookable_space", product__isnull=True, asset__isnull=True, room__isnull=False))


class RoomOutage(models.Model):
    class Mode(models.TextChoices):
        BLOCK = "block", "Block new bookings"
        WARN = "warn", "Warn bookers"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="room_outages")
    room = models.ForeignKey("bookings.BookableSpace", on_delete=models.CASCADE, related_name="outages")
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.BLOCK)
    reason = models.CharField(max_length=300, blank=True)
    expected_back_at = models.DateTimeField(null=True, blank=True)
    issue = models.ForeignKey("maintenance.IssueReport", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="room_outages")
    started_at = models.DateTimeField(default=timezone.now)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    ended_at = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["room"], condition=Q(ended_at__isnull=True),
                                               name="room_outage_one_open")]


class SubjectMaintenanceSchedule(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="subject_maintenance_schedules")
    subject_type = models.CharField(max_length=24, choices=ITEM_SUBJECTS)
    product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="+")
    asset = models.ForeignKey("inventory.InventoryAsset", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="+")
    room = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="+")
    description = models.TextField()
    interval_days = models.PositiveIntegerField()
    next_due = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_due", "id"]
        constraints = [
            models.CheckConstraint(name="subject_schedule_one_subject", condition=_SUBJECT_SHAPE),
            models.CheckConstraint(name="subject_schedule_interval_positive", condition=Q(interval_days__gt=0)),
        ]


class SubjectMaintenanceLog(AppendOnly):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="subject_maintenance_logs")
    schedule = models.ForeignKey(SubjectMaintenanceSchedule, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="logs")
    subject_type = models.CharField(max_length=24, choices=ITEM_SUBJECTS)
    product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="+")
    asset = models.ForeignKey("inventory.InventoryAsset", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="+")
    room = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="+")
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    performed_at = models.DateTimeField(default=timezone.now)
    summary = models.TextField()
    parts_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at", "-id"]
        constraints = [models.CheckConstraint(name="subject_log_one_subject", condition=_SUBJECT_SHAPE)]
