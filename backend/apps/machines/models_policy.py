"""Tenant/type policy; built-in machine types remain global and structural.

Reminder timing (release 1) plus the per-type job settings of the uniform job flow
(#140-#142). Money-shaped choices (quotes, prepay, failure charging) are Space-Manager
settings (`charges.*` keys in the settings-authority layer).
"""

from django.utils.translation import gettext_lazy
from django.db import models


class MakerspaceMachineTypePolicy(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    machine_type = models.ForeignKey("machines.MachineType", on_delete=models.CASCADE)
    # Null retains the reminder defaults after explicit feature opt-in; zero disables
    # advance notices while overdue/expired notifications remain available.
    cert_reminder_days = models.PositiveSmallIntegerField(null=True, blank=True)
    reminder_lead_days = models.PositiveSmallIntegerField(null=True, blank=True)
    grace_days = models.PositiveSmallIntegerField(null=True, blank=True)

    class QuoteMode(models.TextChoices):
        AUTO = "auto", gettext_lazy("Always when priced, off when free")
        OFF = "off", "Off"
        ABOVE = "above", gettext_lazy("Above an amount")
        ALWAYS = "always", "Always"

    class PaymentTiming(models.TextChoices):
        COMPLETION = "completion", gettext_lazy("Pay at completion")
        PREPAY = "prepay", gettext_lazy("Pay before the job queues")

    class FailureCharge(models.TextChoices):
        NONE = "none", gettext_lazy("No charge")
        MATERIAL_ONLY = "material_only", gettext_lazy("Material used only")
        FULL = "full", gettext_lazy("Full charge")

    # #140: on/off per machine type (default on: today every active queue accepts jobs).
    accepts_job_requests = models.BooleanField(default=True)
    quote_mode = models.CharField(max_length=8, choices=QuoteMode.choices, default=QuoteMode.AUTO)
    quote_above_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    payment_timing = models.CharField(max_length=12, choices=PaymentTiming.choices,
                                      default=PaymentTiming.COMPLETION)
    # #142 OQ-8: what a member/file fault costs (a space or machine fault is always free).
    member_fault_charge = models.CharField(max_length=16, choices=FailureCharge.choices,
                                           default=FailureCharge.NONE)
    # #142 OQ-10: off by default (null).
    max_open_jobs = models.PositiveSmallIntegerField(null=True, blank=True)
    max_job_minutes = models.PositiveIntegerField(null=True, blank=True)
    # #142 OQ-11: null = the built-in default (printers run unattended, everything else not).
    runs_unattended = models.BooleanField(null=True, blank=True)
    # #142 OQ-12: maker_formats groups accepted; empty = the type's built-in default.
    file_groups = models.JSONField(default=list, blank=True)
    # Lane L23 (#158.5): a live session stops itself after this many minutes (flagged).
    session_max_minutes = models.PositiveIntegerField(default=240)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["makerspace", "machine_type"], name="machine_type_policy_unique",
        )]
