"""Series passes (release 2 L6, G31): one purchase admits the buyer to every future occurrence.

A pass is an order line of kind `pass`; each covered occurrence gets one seat and one
ordinary registration with no charge of its own. Cancelling an occurrence opens a due
for each pass holder with `occurrence_refund_amount` (the organiser's partial amount),
which staff approve as a refund case. Per-occurrence tickets keep the full-amount rule.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class EventPassType(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    series = models.ForeignKey("events.EventSeries", on_delete=models.CASCADE, related_name="pass_types")
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    #: 0 = unlimited passes.
    capacity = models.PositiveIntegerField(default=0)
    #: Entered by the organiser: what a holder is owed when one occurrence is cancelled.
    occurrence_refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                                   validators=[MinValueValidator(0)])
    sales_end_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["series_id", "pk"]
        constraints = [models.CheckConstraint(condition=Q(amount__gte=0, occurrence_refund_amount__gte=0),
                                              name="event_pass_amounts_nonnegative")]
