"""Booking credentials/projection and immutable, credential-free arrival history."""

from django.utils.translation import gettext_lazy
from uuid import uuid4

from django.conf import settings
from django.db import models


class BookingArrivalFields(models.Model):
    # Separate from the public identity and from every calendar credential.
    checkin_token = models.UUIDField(default=uuid4, editable=False, unique=True)
    arrived_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True


class BookingCheckInEvent(models.Model):
    class Action(models.TextChoices):
        ARRIVED = "arrived", gettext_lazy("Arrival confirmed")
        REVERSED = "reversed", gettext_lazy("Arrival reversed")

    booking = models.ForeignKey("bookings.Booking", on_delete=models.PROTECT,
                                related_name="check_in_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=8, choices=Action.choices)
    source = models.CharField(max_length=16, default="staff_qr", editable=False)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recorded_at", "pk"]
        constraints = [models.CheckConstraint(
            condition=models.Q(action__in=("arrived", "reversed"), source="staff_qr"),
            name="booking_arrival_action_source",
        )]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise RuntimeError("BookingCheckInEvent rows are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("BookingCheckInEvent rows are append-only.")
