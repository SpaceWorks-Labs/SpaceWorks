"""Pricing configuration (lane L15, decisions #84/#85): rate cards and per-item overrides.

These rows hold CONFIGURATION only. Money owed is still one `Payment` per charge; the
resolver (`apps.payments.pricing`) reads these rows, the legacy price fields that already
exist (`MakerspacePaymentSettings.loan_*`, `InventoryProduct.deposit_amount`,
`BookableSpace.payment_amount`, `MakerspaceMachineTypePricing`) and the discount rules,
and freezes the result on the charge it raises.

* `PricingDefault` -- one row per space and domain: free or paid, plus the per-space
  choices that only make sense for one domain (loan `rental_timing`, A1; the machine
  `failed_job_charge`, A11 / #142 OQ-8). No row means "nothing configured": the domain's
  legacy fields still apply and every new component is free.
* `PricingDefaultLine` -- the space's rate for one component (amount, cap, grace, billing
  increment, minimum).
* `PriceOverride` -- inherit / free / custom for one component on one item.
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class PricingDomain(models.TextChoices):
    LOANS = "loans", "Lending"
    MACHINES = "machines", "Machines"
    BOOKINGS = "bookings", "Bookings"
    EVENTS = "events", "Events"
    MEMBERSHIP = "membership", "Membership"


class PricingDefault(models.Model):
    class Mode(models.TextChoices):
        FREE = "free", "Free"
        PAID = "paid", "Paid"

    class RentalTiming(models.TextChoices):
        AT_CHECKOUT = "at_checkout", "At checkout, for the planned days"
        AT_RETURN = "at_return", "At return, for the actual days"

    class FailedJobCharge(models.TextChoices):
        NONE = "none", "No charge"
        MATERIAL_ONLY = "material_only", "Material used only"
        FULL = "full", "Full charge"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="pricing_defaults")
    domain = models.CharField(max_length=16, choices=PricingDomain.choices)
    mode = models.CharField(max_length=8, choices=Mode.choices, default=Mode.FREE)
    #: Lending only (A1). Applies to loans issued after it changes.
    rental_timing = models.CharField(max_length=16, choices=RentalTiming.choices, blank=True, default="")
    #: Machines only (A11, #142 OQ-8): the space default; L12 picks per type and fault.
    failed_job_charge = models.CharField(max_length=16, choices=FailedJobCharge.choices, blank=True, default="")
    updated_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "domain"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "domain"], name="pricing_default_one_per_domain"),
            models.CheckConstraint(condition=Q(domain="loans") | Q(rental_timing=""),
                                   name="pricing_default_rental_timing_loans_only"),
            models.CheckConstraint(condition=Q(domain="machines") | Q(failed_job_charge=""),
                                   name="pricing_default_failed_job_machines_only"),
        ]

    def __str__(self):
        return f"Pricing {self.domain} ({self.mode}) for makerspace {self.makerspace_id}"


class PricingDefaultLine(models.Model):
    default = models.ForeignKey(PricingDefault, on_delete=models.CASCADE, related_name="lines")
    component = models.CharField(max_length=32)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    #: Optional ceiling (per unit of each item line for rentals, per loan for late fees,
    #: per day for hourly bookings). Null means no cap.
    cap = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    #: Free units before a per-day fee starts (late fees: grace days).
    grace_units = models.PositiveIntegerField(default=0)
    #: Round metered time UP to this many minutes (0 or 1 means per minute).
    billing_increment = models.PositiveIntegerField(default=0)
    #: Bill at least this many minutes of metered time.
    minimum = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["default_id", "component"]
        constraints = [
            models.UniqueConstraint(fields=["default", "component"], name="pricing_line_one_per_component"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="pricing_line_amount_nonnegative"),
            models.CheckConstraint(condition=Q(cap__isnull=True) | Q(cap__gte=0), name="pricing_line_cap_nonnegative"),
        ]


class PriceOverride(models.Model):
    """Free / custom for one component on one item (A9, A13).

    The item is one of four real foreign keys, named by `target_type` (a check keeps the
    two in step), so an item's prices remap with it in a tenant move and go when the item
    is deleted. `clean()` proves the item belongs to this space. "Inherit" is the absence
    of a row.
    """

    class TargetType(models.TextChoices):
        INVENTORY_PRODUCT = "inventory_product", "Inventory item"
        MACHINE = "machine", "Machine"
        CONSUMABLE_POOL = "consumable_pool", "Material pool"
        BOOKABLE_SPACE = "bookable_space", "Room or resource"

    class Mode(models.TextChoices):
        INHERIT = "inherit", "Use the space default"
        FREE = "free", "Free"
        CUSTOM = "custom", "Custom price"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="price_overrides")
    domain = models.CharField(max_length=16, choices=PricingDomain.choices)
    component = models.CharField(max_length=32)
    target_type = models.CharField(max_length=24, choices=TargetType.choices)
    product = models.ForeignKey("inventory.InventoryProduct", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="price_overrides")
    machine = models.ForeignKey("machines.Machine", null=True, blank=True, on_delete=models.CASCADE,
                                related_name="price_overrides")
    pool = models.ForeignKey("machines.MachineConsumablePool", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="price_overrides")
    room = models.ForeignKey("bookings.BookableSpace", null=True, blank=True, on_delete=models.CASCADE,
                             related_name="price_overrides")
    mode = models.CharField(max_length=8, choices=Mode.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cap = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    updated_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "target_type", "component", "pk"]
        constraints = [
            *(models.UniqueConstraint(fields=["component", field], condition=Q(**{f"{field}__isnull": False}),
                                      name=f"price_override_one_per_{field}_component")
              for field in ("product", "machine", "pool", "room")),
            models.CheckConstraint(condition=(
                Q(target_type="inventory_product", product__isnull=False, machine__isnull=True, pool__isnull=True,
                  room__isnull=True)
                | Q(target_type="machine", product__isnull=True, machine__isnull=False, pool__isnull=True,
                    room__isnull=True)
                | Q(target_type="consumable_pool", product__isnull=True, machine__isnull=True, pool__isnull=False,
                    room__isnull=True)
                | Q(target_type="bookable_space", product__isnull=True, machine__isnull=True, pool__isnull=True,
                    room__isnull=False)), name="price_override_one_target"),
            models.CheckConstraint(condition=(Q(mode="custom", amount__isnull=False, amount__gte=0)
                                              | (~Q(mode="custom") & Q(amount__isnull=True))),
                                   name="price_override_amount_matches_mode"),
            models.CheckConstraint(condition=Q(cap__isnull=True) | Q(cap__gte=0), name="price_override_cap_nonnegative"),
        ]

    #: target_type -> the foreign key that holds the item.
    FIELDS = {"inventory_product": "product", "machine": "machine", "consumable_pool": "pool",
              "bookable_space": "room"}

    @property
    def target_id(self):
        return getattr(self, f"{self.FIELDS[self.target_type]}_id")

    @property
    def target(self):
        return getattr(self, self.FIELDS[self.target_type])

    def clean(self):
        target = self.target if self.target_type in self.FIELDS else None
        if target is None or target.makerspace_id != self.makerspace_id:
            raise ValidationError({"target_type": "The item must belong to this makerspace."})
