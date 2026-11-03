"""Ticket transfers (release 2 L6, G32): a registration handed to another account.

The sender names an email; the recipient signs in and accepts with the emailed token.
Acceptance moves the registration to the recipient, rotates its credential, voids the
old ID card and re-issues certificates through the existing services. The money stays
with the original payer. A recipient never exists without an account (#71).
"""

import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin


class EventTicketTransfer(ScopedPiiModelMixin, models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Waiting for the recipient"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    registration = models.ForeignKey("events.EventRegistration", on_delete=models.CASCADE, related_name="transfers")
    from_member = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    to_email = models.TextField()
    #: SHA-256 of the emailed acceptance token (random until the invite mints one).
    token_digest = models.CharField(max_length=64, unique=True, default=secrets.token_hex, editable=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="+")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["registration"], condition=Q(status="pending"),
                                    name="event_ticket_transfer_one_pending"),
        ]
