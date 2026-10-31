"""Chargebacks and payment disputes: a RECORD, never an action (lane L5, G25).

A provider tells us a payer disputed a charge. The ledger records it, flags the charge
(and so any ticket or booking it paid for), and notifies staff. It never cancels the
subject, never refunds, and never changes the Payment: the provider moves the disputed
money itself, and the outcome arrives as later status events. `PaymentDisputeEvent` is
the append-only history; `PaymentDispute.status` is the latest of it.
"""

from django.core.exceptions import ValidationError
from django.db import models


class PaymentDispute(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Needs response"
        UNDER_REVIEW = "under_review", "Under review"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        CLOSED = "closed", "Closed"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    payment = models.ForeignKey("payments.Payment", on_delete=models.CASCADE, related_name="disputes")
    provider = models.CharField(max_length=16)
    provider_dispute_id = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    reason = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    provider_status = models.CharField(max_length=32, blank=True, default="")
    evidence_due_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-opened_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["provider", "provider_dispute_id"], name="dispute_once_per_provider"),
        ]
        indexes = [models.Index(fields=["makerspace", "status"], name="dispute_space_status_idx")]

    def delete(self, *args, **kwargs):
        raise ValidationError("Disputes are permanent records.")


class PaymentDisputeEvent(models.Model):
    dispute = models.ForeignKey(PaymentDispute, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=16, choices=PaymentDispute.Status.choices)
    provider_status = models.CharField(max_length=32, blank=True, default="")
    provider_event_id = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recorded_at", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["dispute", "provider_event_id"], name="dispute_event_once"),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Dispute history is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Dispute history is append-only.")
