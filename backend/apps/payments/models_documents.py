"""Immutable issued financial documents, permanently part of the core ledger."""

from django.utils.translation import gettext, gettext_noop
from django.core.exceptions import ValidationError
from django.db import models
from decimal import Decimal, InvalidOperation


class PaymentDocument(models.Model):
    class Kind(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        CREDIT_NOTE = "credit_note", gettext_noop("Credit note")
        BILL = "bill", "Bill"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    payment = models.ForeignKey("payments.Payment", on_delete=models.CASCADE, related_name="documents")
    settlement = models.ForeignKey("payments.ManualSettlement", null=True, blank=True, on_delete=models.CASCADE)
    refund = models.ForeignKey("payments.Refund", null=True, blank=True, on_delete=models.CASCADE)
    reverses = models.OneToOneField("self", null=True, blank=True, on_delete=models.CASCADE, related_name="reversed_by")
    sequence = models.PositiveBigIntegerField()
    number = models.CharField(max_length=80)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    issuer = models.JSONField(default=dict)
    branding_logo_key = models.CharField(max_length=300, blank=True, default="")
    branding_logo_sha256 = models.CharField(max_length=64, blank=True, default="")
    # Label only, never contact details or embedded user IDs. Ownership is Payment.member.
    payer_label = models.CharField(max_length=150)
    payer_type = models.CharField(max_length=16)
    lines = models.JSONField(default=list)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3)
    settlement_method = models.CharField(max_length=16, blank=True)
    settlement_reference = models.CharField(max_length=64, blank=True)
    money_at = models.DateTimeField()
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT)
    # Frozen at issue from the charge's `tax_snapshot` (lane L5). NULL on every document
    # issued without a live tax policy, which is every release-1 document.
    tax_breakdown = models.JSONField(null=True, blank=True, default=None)
    # Per-financial-year series (Rule 46). Blank/NULL keeps the release-1 single series.
    number_series = models.CharField(max_length=16, blank=True, default="")
    fy_start = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["sequence"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "sequence"], condition=models.Q(
                kind__in=["receipt", "credit_note"], fy_start__isnull=True), name="document_money_sequence"),
            models.UniqueConstraint(fields=["makerspace", "number_series", "fy_start", "sequence"],
                                    condition=models.Q(fy_start__isnull=False), name="document_fy_sequence"),
            models.UniqueConstraint(fields=["makerspace", "sequence"], condition=models.Q(kind="bill"), name="document_bill_sequence"),
            models.UniqueConstraint(fields=["payment"], condition=models.Q(kind="bill"), name="document_bill_once"),
            models.UniqueConstraint(fields=["makerspace", "number"], name="document_space_number"),
            models.UniqueConstraint(fields=["makerspace", "settlement"], condition=models.Q(settlement__isnull=False), name="document_settlement_once"),
            models.UniqueConstraint(fields=["makerspace", "refund"], condition=models.Q(refund__isnull=False), name="document_refund_once"),
            models.UniqueConstraint(fields=["makerspace", "payment"], condition=models.Q(
                settlement__isnull=True, refund__isnull=True, reverses__isnull=True, kind="receipt"), name="document_online_once"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="document_amount_positive"),
            models.CheckConstraint(condition=models.Q(sequence__gt=0), name="document_sequence_positive"),
            # Tax only on documents numbered in an FY series, i.e. issued with tax on.
            models.CheckConstraint(condition=models.Q(tax_breakdown__isnull=True) | models.Q(fy_start__isnull=False),
                                   name="document_tax_on_fy_series"),
            models.CheckConstraint(condition=models.Q(fy_start__isnull=True, number_series="") | models.Q(
                fy_start__isnull=False, number_series__in=["invoice", "credit_note"]), name="document_series_shape"),
        ]

    def clean(self):
        import re
        if (bool(self.branding_logo_key) != bool(self.branding_logo_sha256) or
                (self.branding_logo_sha256 and not re.fullmatch(r"[0-9a-f]{64}", self.branding_logo_sha256))):
            raise ValidationError(gettext("Invalid document logo identity."))
        if sum(bool(source) for source in (self.settlement_id, self.refund_id, self.reverses_id)) > 1:
            raise ValidationError(gettext("A document must have only one financial source."))
        if (not isinstance(self.issuer, dict) or not isinstance(self.issuer.get("name"), str)
                or not self.issuer["name"].strip() or any(
                    not isinstance(self.issuer.get(key, ""), str) for key in ("address", "tax_id", "footer"))):
            raise ValidationError(gettext("Invalid document issuer snapshot."))
        if self.payment_id and self.payment.makerspace_id != self.makerspace_id:
            raise ValidationError(gettext("Document must belong to the payment's makerspace."))
        for source in (self.settlement, self.refund, self.reverses):
            if source and source.payment_id != self.payment_id:
                raise ValidationError(gettext("Document sources must refer to the same payment."))
        if self.currency != self.payment.currency:
            raise ValidationError(gettext("Document must match the payment's currency."))
        if self.kind == "bill":
            if (self.payment.status != "pending" or self.amount != self.payment.amount or
                    self.settlement_id or self.refund_id or self.reverses_id):
                raise ValidationError(gettext("A bill must match a pending charge without a financial source."))
        elif self.payment.status not in ("paid_online", "paid_offline"):
            raise ValidationError(gettext("Document must match a collected payment's currency."))
        if self.reverses:
            if ({self.kind, self.reverses.kind} != {"receipt", "credit_note"}
                    or self.amount != self.reverses.amount):
                raise ValidationError(gettext("A reversal must offset the original document exactly."))
        elif self.refund:
            if self.kind != "credit_note" or self.refund.status != "succeeded" or self.amount != self.refund.amount:
                raise ValidationError(gettext("A credit note must match a succeeded refund."))
        elif self.kind not in ("receipt", "bill") or (
                self.amount != self.payment.amount and not self._received_amount_released()):
            raise ValidationError(gettext("A receipt must match the full collected amount."))
        if self.settlement and (self.kind != "receipt" or self.amount != self.settlement.amount):
            raise ValidationError(gettext("A settlement receipt must match its settlement."))
        try:
            if not self.lines or not isinstance(self.lines, list) or len(self.lines) > 200 or any(
                not isinstance(line, dict) or not isinstance(line.get("label"), str) or
                not line["label"].strip() or
                not all(Decimal(line[key]).is_finite() for key in ("quantity", "unit_amount", "total")) or
                Decimal(line["quantity"]) <= 0 or Decimal(line["unit_amount"]) < 0 or
                Decimal(line["quantity"]) * Decimal(line["unit_amount"]) != Decimal(line["total"])
                for line in self.lines
            ) or sum(Decimal(line["total"]) for line in self.lines) != Decimal(self.amount):
                raise ValidationError(gettext("Document lines must reconcile to the total."))
        except (InvalidOperation, TypeError, KeyError, ValueError):
            raise ValidationError(gettext("Invalid document lines."))

    def _received_amount_released(self):
        """Staff released a held receipt on the amount actually received (capture flag)."""
        from apps.payments.models_capture_flags import PaymentCaptureFlag
        return PaymentCaptureFlag.objects.filter(
            payment_id=self.payment_id, resolution=PaymentCaptureFlag.Resolution.ISSUE_RECEIVED,
            captured_amount=self.amount).exists()

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(gettext("Payment documents are append-only."))
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(gettext("Payment documents are append-only."))
