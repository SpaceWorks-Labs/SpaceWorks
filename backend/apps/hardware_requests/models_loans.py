"""Loan depth models (release 2, L12): pickup and waitlist timing, and the waitlist.

Inductions before a first loan are NOT built (#96, #128 C-19).
"""

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class LoanReservationPolicy(models.Model):
    """Per-space pickup and waitlist timing. Defaults reproduce release-1 behaviour:
    a pickup window of 0 hours means an accepted request never expires."""

    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="loan_reservation_policy")
    pickup_window_hours = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(720)])
    reservation_max_days_ahead = models.PositiveIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(365)])
    waitlist_offer_hours = models.PositiveIntegerField(
        default=48, validators=[MinValueValidator(1), MaxValueValidator(336)])
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def for_makerspace(cls, makerspace):
        return cls.objects.filter(makerspace=makerspace).first() or cls(makerspace=makerspace)


class LoanWaitlistEntry(models.Model):
    """A member queued, first come first served, for a product with no free stock.

    An ``offered`` entry holds ``held_quantity`` units in the product's reserved bucket
    (through the availability module) until it is claimed by a request, lapses, or is
    left. Accepting the claiming request turns the hold into that request's reservation.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", "Waiting"
        OFFERED = "offered", "Offered"
        CLAIMED = "claimed", "Claimed"
        FULFILLED = "fulfilled", "Fulfilled"
        LAPSED = "lapsed", "Lapsed"
        CANCELLED = "cancelled", "Cancelled"

    ACTIVE = (Status.WAITING, Status.OFFERED, Status.CLAIMED)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="loan_waitlist_entries")
    product = models.ForeignKey("inventory.InventoryProduct", on_delete=models.CASCADE,
                                related_name="waitlist_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(99)])
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.WAITING)
    held_quantity = models.PositiveIntegerField(default=0)
    offered_at = models.DateTimeField(null=True, blank=True)
    offer_expires_at = models.DateTimeField(null=True, blank=True)
    request = models.ForeignKey("hardware_requests.HardwareRequest", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["product", "user"], condition=Q(status__in=["waiting", "offered", "claimed"]),
                                    name="uniq_active_waitlist_entry"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="waitlist_quantity_positive"),
            models.CheckConstraint(condition=Q(held_quantity=0) | Q(status__in=["offered", "claimed"]),
                                   name="waitlist_hold_only_when_offered"),
        ]
        indexes = [models.Index(fields=["product", "status", "created_at"], name="waitlist_queue_idx")]
