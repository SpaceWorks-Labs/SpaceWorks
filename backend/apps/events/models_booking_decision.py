"""Event-owned retained decision: a booking is the sole venue-fee owner."""
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext


class EventBookingDecision(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    event = models.OneToOneField("events.Event", on_delete=models.CASCADE)
    booking = models.OneToOneField("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    operation_id = models.UUIDField()
    generation = models.UUIDField(default=uuid4, editable=False, unique=True)
    revision = models.PositiveBigIntegerField(default=1)
    billing_owner = models.CharField(max_length=12, default="booking", editable=False)
    intent_version = models.PositiveSmallIntegerField(default=1, editable=False)
    intent = models.JSONField(default=dict, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(gettext("Booking decisions are immutable."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Booking decisions are retained until authorized purge."))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("makerspace", "operation_id"), name="event_booking_operation_uniq"),
            models.CheckConstraint(condition=Q(revision=1), name="event_booking_revision_ck"),
            models.CheckConstraint(condition=Q(billing_owner="booking"), name="event_booking_owner_ck"),
        ]
