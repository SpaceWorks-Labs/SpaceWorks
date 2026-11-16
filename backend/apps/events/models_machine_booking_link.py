"""Event-owned link to a machine-time booking used by a workshop (P2-1).

Sibling of `EventBookingDecision`, never a second kind of it: that decision is one per
event, names the ONE room whose Booking owns the venue charge, and freezes an intent for
replay. A workshop may also hold any number of machine bookings; each keeps its own
Booking-owned machine-time charge through ordinary booking pricing, so this row carries
no billing owner, no intent and no money. It is written once and never edited; a purged
booking leaves the row naming nothing (`booking` NULL, shown as unavailable), exactly as
the room decision is detached.

Decision 221b: unlinking never deletes or edits the link's facts. The one permitted update
is the one-way `unlinked_at` marker (`end`); the row stays as history, the booking itself is
untouched, and only a live (unlinked_at NULL) row holds the booking -- so the booking may
be linked again later as a new row.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext


class EventMachineBookingLink(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT)
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="machine_booking_links")
    booking = models.ForeignKey("bookings.Booking", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="event_machine_links")
    created_at = models.DateTimeField(auto_now_add=True)
    unlinked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["booking"], condition=Q(unlinked_at__isnull=True, booking__isnull=False),
            name="event_machine_link_live_booking_uniq")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(gettext("Workshop machine links are immutable."))
        return super().save(*args, **kwargs)

    def end(self):
        """Mark a live link unlinked, once. Every other field is left exactly as written."""
        if self._state.adding or self.unlinked_at is not None:
            raise ValidationError(gettext("Only a live workshop machine link can be unlinked."))
        self.unlinked_at = timezone.now()
        updated = type(self).objects.filter(pk=self.pk, unlinked_at__isnull=True).update(unlinked_at=self.unlinked_at)
        if updated != 1:
            raise ValidationError(gettext("Only a live workshop machine link can be unlinked."))
        return self

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Workshop machine links are retained until authorized purge."))
