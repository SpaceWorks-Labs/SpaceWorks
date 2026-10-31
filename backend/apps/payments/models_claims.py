"""A payer's "I've paid" claim for an offline transfer (lane L5, G23).

The claim moves nothing. It tells staff that a UPI or bank transfer was sent, with its
reference (the UTR), so they can check their account and confirm or reject it. Only a
staff confirmation writes the `ManualSettlement` receipt -- through the maker-checker
step when the space requires one. A reference can be claimed once per space, ever: a
second claim quoting the same UTR is refused, whatever happened to the first.
"""

from django.core.exceptions import ValidationError
from django.db import models


class PaymentClaim(models.Model):
    class Method(models.TextChoices):
        UPI = "upi", "UPI"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Waiting for staff"
        AWAITING_CONFIRMATION = "awaiting_confirmation", "Waiting for a second confirmation"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"

    OPEN_STATUSES = (Status.SUBMITTED, Status.AWAITING_CONFIRMATION)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    payment = models.ForeignKey("payments.Payment", on_delete=models.CASCADE, related_name="claims")
    #: The signed-in payer, or NULL for a claim made through an account-less pay link.
    claimant = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    pay_link = models.ForeignKey("payments.PaymentPayLink", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="claims")
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.UPI)
    #: Upper-cased, spaces removed. A payment reference, never contact details.
    reference = models.CharField(max_length=35)
    paid_on = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.SUBMITTED)
    decided_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    decided_at = models.DateTimeField(null=True, blank=True)
    #: Staff-authored, shown to the payer. Financial context only.
    decision_note = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "reference"], name="payment_claim_reference_once"),
            models.UniqueConstraint(fields=["payment"], condition=models.Q(
                status__in=["submitted", "awaiting_confirmation"]), name="payment_claim_one_open"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="payment_claim_amount_positive"),
        ]
        indexes = [models.Index(fields=["makerspace", "status"], name="payment_claim_queue_idx")]

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment claims are permanent records.")
