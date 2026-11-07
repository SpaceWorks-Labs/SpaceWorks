"""Per-space tax policy and the per-financial-year document counters (core ledger)."""

from django.utils.translation import gettext_noop
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models

from apps.payments.tax.gstin import GstinError, validate_gstin, validate_state_code

PREFIX_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-/"


class MakerspaceTaxSettings(models.Model):
    """What tax the space charges. Read only while the `billing.tax` capability is on.

    Frozen onto each new charge as `Payment.tax_snapshot`; editing this row never
    changes a charge that already exists or a document already issued.
    """

    class Mode(models.TextChoices):
        NONE = "none", gettext_noop("No tax")
        SINGLE = "single", gettext_noop("Single named tax")
        GST_INDIA = "gst_india", gettext_noop("India GST")

    class Scheme(models.TextChoices):
        REGULAR = "regular", "Regular"
        COMPOSITION = "composition", "Composition"

    class ForeignCurrency(models.TextChoices):
        NO_GST = "no_gst", gettext_noop("Outside GST")
        EXPORT_LUT = "export_lut", gettext_noop("Export under LUT")

    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="tax_settings")
    mode = models.CharField(max_length=16, choices=Mode.choices, default=Mode.NONE)
    tax_name = models.CharField(max_length=32, blank=True, default="")
    rate_bps = models.PositiveIntegerField(default=1800, validators=[MaxValueValidator(10000)])
    prices_include_tax = models.BooleanField(default=True)
    gstin = models.CharField(max_length=15, blank=True, default="")
    state_code = models.CharField(max_length=2, blank=True, default="")
    scheme = models.CharField(max_length=16, choices=Scheme.choices, default=Scheme.REGULAR)
    exempt = models.BooleanField(default=False)
    sac_code = models.CharField(max_length=8, default="999599")
    foreign_currency = models.CharField(max_length=16, choices=ForeignCurrency.choices, default=ForeignCurrency.NO_GST)
    lut_number = models.CharField(max_length=32, blank=True, default="")
    invoice_prefix = models.CharField(max_length=4, default="INV")
    credit_note_prefix = models.CharField(max_length=4, default="CN")
    updated_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(rate_bps__lte=10000), name="tax_rate_bps_range"),
            models.CheckConstraint(condition=~models.Q(invoice_prefix=models.F("credit_note_prefix")),
                                   name="tax_series_prefixes_differ"),
        ]

    def clean(self):
        errors = {}
        for name in ("invoice_prefix", "credit_note_prefix"):
            value = getattr(self, name) or ""
            if not value or len(value) > 4 or any(char not in PREFIX_CHARS for char in value):
                errors[name] = "Use 1 to 4 capital letters, digits, '-' or '/'."
        if self.invoice_prefix == self.credit_note_prefix:
            errors["credit_note_prefix"] = "Invoice and credit-note prefixes must differ."
        if not self.sac_code.isdigit() or not 4 <= len(self.sac_code) <= 8:
            errors["sac_code"] = "A SAC code is 4 to 8 digits."
        if self.mode == self.Mode.SINGLE:
            if not self.tax_name.strip():
                errors["tax_name"] = "Name the tax, for example VAT."
        if self.mode == self.Mode.GST_INDIA:
            try:
                self.gstin = validate_gstin(self.gstin)
                self.state_code = validate_state_code(self.state_code or self.gstin[:2])
                if self.gstin[:2] != self.state_code:
                    errors["state_code"] = "The state must match the GSTIN's state code."
            except GstinError as exc:
                errors["state_code" if exc.code == "state_code_invalid" else "gstin"] = str(exc)
            if self.foreign_currency == self.ForeignCurrency.EXPORT_LUT and not self.lut_number.strip():
                errors["lut_number"] = "Exports under LUT need the LUT reference number."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DocumentNumberCounter(models.Model):
    """Gapless per-financial-year series. Locked and bumped inside the issue transaction."""

    class Series(models.TextChoices):
        INVOICE = "invoice", gettext_noop("Tax invoice / receipt")
        CREDIT_NOTE = "credit_note", gettext_noop("Credit note")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    series = models.CharField(max_length=16, choices=Series.choices)
    fy_start = models.DateField()
    next_number = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "series", "fy_start"], name="document_counter_once"),
            models.CheckConstraint(condition=models.Q(next_number__gt=0), name="document_counter_positive"),
        ]
