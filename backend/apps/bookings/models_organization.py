"""Decision 223 (k), lane L3b: the organization that booked a space for a partner event.

An adapter row, one per booking, so the `Booking` table itself is untouched. Organizations have no
ledger account of their own (`Payment.member` is a person), so the debt is recorded against the
organization's named contact member (`billed_member`) exactly like any member booking, and this row
records WHICH organization the booking was for. Reports and calendars read the organization here.
"""
from django.conf import settings
from django.db import models


class BookingOrganizationLink(models.Model):
    booking = models.OneToOneField("bookings.Booking", on_delete=models.CASCADE, related_name="organization_link")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="+")
    #: The organization's name when booked: survives the organization being renamed or removed.
    organization_name = models.CharField(max_length=200)
    billed_member = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["makerspace", "organization"], name="booking_org_link_idx")]
