"""Ticket add-ons (release 2 L6, G30): kit, lunch, T-shirts with variants, session seats.

Stock is EVENT-LOCAL: a count on the add-on (or on each variant), 0 meaning unlimited,
sold down by paid and held order lines. An add-on never touches hardware inventory; kit
that really comes from inventory must go through `inventory/availability.py` (not here).
"""

from django.utils.translation import gettext_lazy
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class EventAddon(models.Model):
    class Kind(models.TextChoices):
        KIT = "kit", "Kit"
        MEAL = "meal", "Meal"
        MERCH = "merch", "Merchandise"
        SESSION = "session", gettext_lazy("Session seat")
        OTHER = "other", "Other"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="addons")
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=300, blank=True, default="")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.OTHER)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    #: 0 = unlimited. Ignored when the add-on has variants: each variant keeps its own stock.
    stock = models.PositiveIntegerField(default=0)
    per_order_limit = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_id", "pk"]
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0), name="event_addon_nonnegative")]


class EventAddonVariant(models.Model):
    addon = models.ForeignKey(EventAddon, on_delete=models.CASCADE, related_name="variants")
    label = models.CharField(max_length=60)
    stock = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["addon_id", "pk"]
        constraints = [models.UniqueConstraint(fields=["addon", "label"], name="event_addon_variant_unique_label")]
