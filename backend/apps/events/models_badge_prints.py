"""Badge print receipts (parity E-B2): which badge was printed, where, and by what route.

Append-only evidence that a desk, a PIN station, an offline desk or a bulk job printed one badge. It
holds no name, photo or answer: only ids, the stock and the role the badge was printed for. A receipt
is idempotent by `operation_id` (a device that retries, or syncs an offline queue, never double-counts).
The monthly `event_badge_prints_monthly` limit counts these rows.
"""
from uuid import uuid4

from django.conf import settings
from django.db import models


class EventBadgePrint(models.Model):
    class Method(models.TextChoices):
        DESK = "desk", "Desk"
        STATION = "station", "Station"
        OFFLINE = "offline", "Offline desk"
        BULK = "bulk", "Bulk job"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event = models.ForeignKey("events.Event", on_delete=models.CASCADE, related_name="badge_prints")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, related_name="badge_prints")
    card = models.ForeignKey("events.EventIdCard", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="badge_prints")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="+")
    method = models.CharField(max_length=8, choices=Method.choices)
    stock = models.CharField(max_length=32, blank=True, default="")
    role = models.CharField(max_length=12, blank=True, default="")
    operation_id = models.UUIDField(default=uuid4, editable=False)
    printed_at = models.DateTimeField()
    reported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["event_id", "pk"]
        constraints = [models.UniqueConstraint(fields=["event", "operation_id"],
                                               name="event_badge_print_operation")]
        indexes = [models.Index(fields=["makerspace", "reported_at"], name="eventbadgeprint_space_month_idx")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Badge print receipts are append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Badge print receipts are append-only.")
