"""Seat holds while a buyer pays (release 2 L6, G28).

One hold per order, sized to the provider's minimum checkout session (30 minutes for
Stripe Checkout). Live holds count against event and ticket capacity in
`capacity.held_seats`; payment, expiry, failure or cancellation releases them. With
`events.seat_holds` off no hold is written and seats are taken only when payment lands.
"""

from django.utils.translation import gettext_noop
from django.db import models
from django.db.models import Q


class EventCheckoutHold(models.Model):
    class Reason(models.TextChoices):
        PAID = "paid", "Paid"
        EXPIRED = "expired", "Expired"
        FAILED = "failed", gettext_noop("Payment failed")
        CANCELLED = "cancelled", "Cancelled"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    order = models.OneToOneField("events.EventOrder", on_delete=models.CASCADE, related_name="hold")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="checkout_holds")
    seats = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    released_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.CharField(max_length=12, choices=Reason.choices, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expires_at", "pk"]
        indexes = [models.Index(fields=["event", "released_at", "expires_at"], name="event_hold_live_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(seats__gte=1), name="event_hold_positive"),
            models.CheckConstraint(condition=(Q(released_at__isnull=True, release_reason="")
                                              | (Q(released_at__isnull=False) & ~Q(release_reason=""))),
                                   name="event_hold_release_shape"),
        ]
