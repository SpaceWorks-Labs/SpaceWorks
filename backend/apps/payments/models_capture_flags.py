"""Online money that arrived in a way the ledger did not expect (lane L5, G24).

A capture is never refused: the money is already at the provider. It is ACCEPTED --
recorded against its charge -- and FLAGGED, and the receipt is HELD until a staff member
decides: issue the receipt on the amount actually received, open a refund case (which a
staff member still has to approve before any money moves), or acknowledge it with a
note (for example, refunded in the provider dashboard). Nothing here refunds anything.

Kinds:
* `late` -- the charge had been cancelled when the money arrived.
* `duplicate` -- a second, different capture for a charge already paid.
* `mismatch` -- the captured amount or currency differs from the charge.
"""

from django.utils.translation import gettext, gettext_lazy
from django.core.exceptions import ValidationError
from django.db import models


class PaymentCaptureFlag(models.Model):
    class Kind(models.TextChoices):
        LATE = "late", gettext_lazy("Paid after cancellation")
        DUPLICATE = "duplicate", gettext_lazy("Paid twice")
        MISMATCH = "mismatch", gettext_lazy("Amount differs")

    class Resolution(models.TextChoices):
        OPEN = "", "Open"
        ISSUE_RECEIVED = "issue_received", gettext_lazy("Receipt issued on the amount received")
        REFUND_CASE = "refund_case", gettext_lazy("Refund case opened")
        ACKNOWLEDGED = "acknowledged", "Acknowledged"

    #: Kinds whose receipt waits for the staff decision. A duplicate's charge already has
    #: its receipt; the second capture simply has none.
    HOLDS_RECEIPT = (Kind.LATE, Kind.MISMATCH)

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    payment = models.ForeignKey("payments.Payment", on_delete=models.CASCADE, related_name="capture_flags")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    provider = models.CharField(max_length=16)
    provider_payment_id = models.CharField(max_length=255, blank=True, default="")
    provider_event_id = models.CharField(max_length=255, blank=True, default="")
    #: What actually arrived, in provider minor units and in ledger units of the charge
    #: currency (NULL when the currency itself differs, so it cannot be receipted).
    captured_minor = models.BigIntegerField(default=0)
    captured_currency = models.CharField(max_length=3, blank=True, default="")
    captured_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    prior_status = models.CharField(max_length=16, blank=True, default="")
    flagged_at = models.DateTimeField(auto_now_add=True)
    resolution = models.CharField(max_length=16, choices=Resolution.choices, blank=True, default="")
    resolution_note = models.CharField(max_length=500, blank=True, default="")
    resolved_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    resolved_at = models.DateTimeField(null=True, blank=True)
    refund_case = models.ForeignKey("payments.RefundCase", null=True, blank=True, on_delete=models.PROTECT,
                                    related_name="+")

    class Meta:
        ordering = ["-flagged_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["payment", "kind", "provider_payment_id"], name="capture_flag_once"),
            models.CheckConstraint(condition=models.Q(resolution="", resolved_at__isnull=True) | models.Q(
                ~models.Q(resolution=""), resolved_at__isnull=False), name="capture_flag_resolution_shape"),
        ]
        indexes = [models.Index(fields=["makerspace", "resolution"], name="capture_flag_open_idx")]

    @property
    def is_open(self):
        return self.resolution == ""

    def save(self, *args, **kwargs):
        if self.pk:
            original = type(self).objects.filter(pk=self.pk).values("resolution").first()
            if original and original["resolution"]:
                raise ValidationError(gettext("A resolved capture flag is final."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Capture flags are permanent records."))
