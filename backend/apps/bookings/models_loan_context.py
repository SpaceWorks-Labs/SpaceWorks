"""Booking-owned association to the core request."""
from django.db import models
from django.db.models import Q

MAX_REVISION = 9007199254740991

class BookingLoanContext(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    request = models.OneToOneField("hardware_requests.HardwareRequest", on_delete=models.PROTECT)
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=False)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(Q(active=True, booking__isnull=False) | Q(active=False, booking__isnull=True)), name="booking_loan_context_active_ck"),
            models.CheckConstraint(condition=Q(revision__gte=1, revision__lte=MAX_REVISION), name="booking_loan_context_revision_ck"),
        ]
