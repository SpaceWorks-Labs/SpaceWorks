"""Ticket templates belong to a series; sellable copies belong to occurrences."""

from django.utils.translation import gettext, gettext_noop
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from apps.payments.money_model import MoneyDecimalField


class EventTicketType(models.Model):
    class Audience(models.TextChoices):
        MEMBER = "member", gettext_noop("Active members")
        PUBLIC = "public", gettext_noop("All accounts")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.CASCADE, related_name="ticket_types")
    series = models.ForeignKey("events.EventSeries", null=True, blank=True, on_delete=models.CASCADE, related_name="ticket_types")
    name = models.CharField(max_length=100)
    amount = MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    audience = models.CharField(max_length=8, choices=Audience.choices, default=Audience.PUBLIC)
    capacity = models.PositiveIntegerField(default=0)
    purpose = models.CharField(max_length=16, default="participant", choices=[
        ("participant", "Participant"), ("contributor", "Contributor")])
    contributor_capacity_policy = models.CharField(max_length=32, default="event_capacity", choices=[
        ("event_capacity", "Event capacity"), ("reserved_contributor_capacity", "Reserved contributor capacity")])
    sales_start_at = models.DateTimeField(null=True, blank=True)
    sales_end_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Release 2 L6 (G29), read only by orders. A tier group chains its tiers by rank: the
    # next one opens when the one before sells out or its sales end.
    tier_group = models.CharField(max_length=64, blank=True, default="")
    tier_rank = models.PositiveSmallIntegerField(default=0)
    pricing_mode = models.CharField(max_length=8, default="fixed", choices=[
        ("fixed", "Fixed price"), ("pwyw", "Pay what you want")])
    #: Pay-what-you-want only: the lowest amount accepted (`amount` is the suggestion).
    min_amount = MoneyDecimalField(max_digits=13, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    #: A group ticket admits this many people, each with their own registration.
    seats_per_ticket = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    #: Hidden tickets are sold only to a buyer holding an access code for this type.
    is_hidden = models.BooleanField(default=False)
    min_quantity = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    #: 0 means no per-order limit beyond the event's own.
    per_order_limit = models.PositiveSmallIntegerField(default=0)

    def clean(self):
        super().clean()
        if self.contributor_capacity_policy == "reserved_contributor_capacity" and (
                self.purpose != "contributor" or self.capacity == 0):
            raise ValidationError({"capacity": gettext("A reserved contributor pool needs a finite positive capacity.")})
        if bool(self.event_id) == bool(self.series_id):
            raise ValidationError(gettext("Choose exactly one event or series owner."))
        for field in ("event", "series"):
            owner = getattr(self, field)
            if owner and owner.makerspace_id != self.makerspace_id:
                raise ValidationError({field: gettext("Owner must belong to this makerspace.")})

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=(Q(contributor_capacity_policy="event_capacity")
                | Q(purpose="contributor", contributor_capacity_policy="reserved_contributor_capacity", capacity__gt=0)),
                name="event_ticket_contributor_pool_shape"),
            models.CheckConstraint(condition=Q(amount__gte=0), name="event_ticket_nonnegative"),
            models.CheckConstraint(condition=(Q(event__isnull=False, series__isnull=True) | Q(event__isnull=True, series__isnull=False)), name="event_ticket_one_owner"),
            models.CheckConstraint(condition=(Q(sales_start_at__isnull=True) | Q(sales_end_at__isnull=True) | Q(sales_end_at__gt=F("sales_start_at"))), name="event_ticket_sales_window"),
            models.CheckConstraint(condition=Q(seats_per_ticket__gte=1, min_quantity__gte=1, min_amount__gte=0),
                                   name="event_ticket_order_shape"),
            models.CheckConstraint(condition=Q(per_order_limit=0) | Q(per_order_limit__gte=F("min_quantity")),
                                   name="event_ticket_order_limit"),
        ]
