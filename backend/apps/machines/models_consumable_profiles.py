"""Per-machine-type consumable profiles, their job usage, and editable type templates (decisions 341/343).

* `MachineTypeConsumable` -- one space's consumable definition for one machine type
  (built-in types are global, so every profile row belongs to a space: the space's own
  override of what that type uses).
* `ServiceRequestConsumableUsage` -- append-only estimates and actuals per job and key.
* `MachineTypeTemplate` -- a space's own copy of a built-in template (or a new one); the
  built-in catalogue itself is the data file `machine_type_templates.json`.

No user FKs: who wrote what is in the audit log, so account merges have nothing to move.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.payments.money_model import MoneyDecimalField

from .consumable_profiles import EstimateBy, Kind, Source, Unit


class MachineTypeConsumable(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="machine_type_consumables")
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.CASCADE,
                                     related_name="consumable_profile")
    key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.MATERIAL)
    unit = models.CharField(max_length=12, choices=Unit.choices)
    # {"material": ["PLA", ...], "colour": [], "thickness": ["3 mm"], "size": []}; [] = free text.
    attributes = models.JSONField(default=dict, blank=True)
    required = models.BooleanField(default=False)
    estimate_by = models.CharField(max_length=8, choices=EstimateBy.choices, default=EstimateBy.NONE)
    record_by = models.JSONField(default=list)
    # Major units of the space's default currency per one `unit`; null = not charged on its own.
    unit_price = MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True,
                                   validators=[MinValueValidator(0)])
    consumable_pool = models.ForeignKey("machines.MachineConsumablePool", null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name="profile_links")
    product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="machine_profile_links")
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    # Provenance only: the template key this row came from ("" = added by hand or migrated).
    template_key = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "machine_type", "key"],
                                    name="machine_type_consumable_key_unique"),
            models.CheckConstraint(condition=Q(unit_price__isnull=True) | Q(unit_price__gte=0),
                                   name="machine_type_consumable_price_nonnegative"),
            models.CheckConstraint(condition=Q(consumable_pool__isnull=True) | Q(product__isnull=True),
                                   name="machine_type_consumable_single_stock"),
        ]

    def __str__(self):
        return f"{self.name} ({self.unit})"


class ServiceRequestConsumableUsageQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise RuntimeError("ServiceRequestConsumableUsage rows are append-only.")

    def delete(self):
        raise RuntimeError("ServiceRequestConsumableUsage rows are append-only.")


class ServiceRequestConsumableUsage(models.Model):
    class Phase(models.TextChoices):
        ESTIMATE = "estimate", "Estimate"
        ACTUAL = "actual", "Actual"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="+")
    service_request = models.ForeignKey("machines.MachineServiceRequest", on_delete=models.PROTECT,
                                        related_name="profile_usage")
    definition = models.ForeignKey(MachineTypeConsumable, on_delete=models.PROTECT, related_name="usage")
    # Snapshots: a later edit of the definition never rewrites what a job used.
    key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=12, choices=Kind.choices)
    unit = models.CharField(max_length=12, choices=Unit.choices)
    phase = models.CharField(max_length=8, choices=Phase.choices)
    quantity = models.DecimalField(max_digits=16, decimal_places=3)
    attributes = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=8, choices=Source.choices)
    unit_price = MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True)
    # Adapter provenance (the device id), never an audit actor.
    device_ref = models.CharField(max_length=36, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ServiceRequestConsumableUsageQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["makerspace", "phase", "created_at"], name="profile_usage_scope_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="profile_usage_quantity_positive"),
            # One actual per job and consumable: the first recorder wins, the stock is debited once.
            models.UniqueConstraint(fields=["service_request", "definition"], condition=Q(phase="actual"),
                                    name="profile_usage_one_actual"),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("ServiceRequestConsumableUsage rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("ServiceRequestConsumableUsage rows are append-only.")


class MachineTypeTemplate(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="machine_type_templates")
    key = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    category = models.CharField(max_length=50, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    # The built-in key this copy shadows ("" for a space's own template).
    based_on = models.CharField(max_length=50, blank=True)
    spec = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [models.UniqueConstraint(fields=["makerspace", "key"], name="machine_type_template_key_unique")]

    def __str__(self):
        return self.name
