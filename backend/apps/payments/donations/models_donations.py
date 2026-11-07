"""Donations (release 2 lane L18; #94, #96, #128 C-14).

A `Donation` is one gift: a one-off gift, or one period of a `DonationPledge`. Money owed is
its ONE `Payment` (subject `donation`, subject_id = the Donation id) raised through the
record-first ledger seam; paid online when `payments.donations` is on, else settled offline
with a `ManualSettlement` receipt. Money never moves back without a staff-approved refund
case (#59). Donor contact details are scoped PII; the 80G PAN is ALWAYS encrypted
(`encryption/registry_r2_l18`, `encryption_required`) and never leaves through a report.
"""

from django.utils.translation import gettext, gettext_noop
import secrets

from django.db import models
from django.db.models import F, Q

from apps.encryption.mappers import ScopedPiiModelMixin
from apps.payments.models_settings import currency_validator


class DonationCampaign(models.Model):
    """An optional campaign (with a goal and a window) or a standing fund a gift goes to."""

    class Kind(models.TextChoices):
        CAMPAIGN = "campaign", "Campaign"
        FUND = "fund", "Fund"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="donation_campaigns")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CAMPAIGN)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=80)
    description = models.TextField(blank=True, default="")
    goal_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, validators=[currency_validator])
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "slug"], name="donation_campaign_slug_unique"),
            models.CheckConstraint(condition=Q(goal_amount__isnull=True) | Q(goal_amount__gt=0),
                                   name="donation_campaign_goal_positive"),
            models.CheckConstraint(condition=Q(starts_at__isnull=True) | Q(ends_at__isnull=True)
                                   | Q(ends_at__gt=F("starts_at")), name="donation_campaign_window"),
        ]


class DonorTaxDetail(ScopedPiiModelMixin, models.Model):
    """The 80G identity a giver gave: PAN (ALWAYS encrypted) and postal address.

    Its own row so that only writing it needs the tenant's encryption key prepared; a gift or a
    pledge points at it (every period gift of a pledge shares the pledge's row).
    """

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    pan = models.TextField(blank=True, default="")
    address = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)


class DonationPledge(ScopedPiiModelMixin, models.Model):
    """A promise to give every period. It raises one charge per period; no card on file (C-14c)."""

    class Interval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        QUARTERLY = "quarterly", "Quarterly"
        YEARLY = "yearly", "Yearly"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        CANCELLED = "cancelled", "Cancelled"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="donation_pledges")
    campaign = models.ForeignKey(DonationCampaign, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="pledges")
    donor = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT,
                              related_name="donation_pledges")
    donor_name = models.TextField(blank=True, default="")
    donor_email = models.TextField(blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, validators=[currency_validator])
    interval = models.CharField(max_length=10, choices=Interval.choices, default=Interval.MONTHLY)
    starts_on = models.DateField()
    next_due_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    wants_tax_receipt = models.BooleanField(default=False)
    tax_detail = models.ForeignKey(DonorTaxDetail, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    #: A random secret bound into a guest's signed manage link (`identity.link_token`). It is
    #: replaced on a tenant move, so links minted elsewhere stop working.
    manage_secret = models.CharField(max_length=64, unique=True, default=secrets.token_hex, editable=False)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    last_reminded_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["status", "next_due_on"], name="donation_pledge_due_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="donation_pledge_amount_positive"),
            models.CheckConstraint(condition=Q(ends_on__isnull=True) | Q(ends_on__gte=F("starts_on")),
                                   name="donation_pledge_window"),
        ]


class Donation(ScopedPiiModelMixin, models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", gettext_noop("Waiting for payment")
        PAID = "paid", "Received"
        CANCELLED = "cancelled", "Cancelled"

    class Source(models.TextChoices):
        ONLINE = "online", gettext_noop("Given online")
        DESK = "desk", gettext_noop("Recorded by staff")
        PLEDGE = "pledge", gettext_noop("Pledge period")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="donations")
    campaign = models.ForeignKey(DonationCampaign, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="donations")
    pledge = models.ForeignKey(DonationPledge, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="donations")
    #: The first day of the pledge period this gift is for (pledge gifts only).
    period_start = models.DateField(null=True, blank=True)
    donor = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT,
                              related_name="donations")
    donor_name = models.TextField(blank=True, default="")
    donor_email = models.TextField(blank=True, default="")
    donor_note = models.TextField(blank=True, default="")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, validators=[currency_validator])
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.ONLINE)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    wants_tax_receipt = models.BooleanField(default=False)
    tax_detail = models.ForeignKey(DonorTaxDetail, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    #: The 80G receipt frozen when the gift was received: registration, validity, number,
    #: amount and date. Never the PAN (it stays encrypted on this row). Insert-once.
    tax_receipt = models.JSONField(null=True, blank=True, default=None)
    #: A random secret bound into a guest donor's signed status link (`identity.link_token`).
    #: Replaced on a tenant move, so links minted elsewhere stop working.
    access_secret = models.CharField(max_length=64, unique=True, default=secrets.token_hex, editable=False)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["makerspace", "status"], name="donation_space_status_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="donation_amount_positive"),
            models.UniqueConstraint(fields=["pledge", "period_start"], condition=Q(pledge__isnull=False),
                                    name="donation_one_per_pledge_period"),
            models.CheckConstraint(condition=Q(tax_receipt__isnull=True) | Q(wants_tax_receipt=True),
                                   name="donation_tax_receipt_requested"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            frozen = type(self).objects.filter(pk=self.pk).values_list("tax_receipt", flat=True).first()
            if frozen is not None and frozen != self.tax_receipt:
                from django.core.exceptions import ValidationError
                raise ValidationError(gettext("A tax-exempt receipt is frozen once issued."))
        return super().save(*args, **kwargs)


class DonationSettings(models.Model):
    """Per-space donation page text and the optional 80G registration (C-14d)."""

    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="donation_settings")
    page_intro = models.CharField(max_length=500, blank=True, default="")
    suggested_amounts = models.JSONField(default=list, blank=True)
    minimum_amount = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    tax_exempt_registration_number = models.CharField(max_length=64, blank=True, default="")
    tax_exempt_valid_from = models.DateField(null=True, blank=True)
    tax_exempt_valid_until = models.DateField(null=True, blank=True)
    tax_exempt_registrant_pan = models.CharField(max_length=10, blank=True, default="")
    tax_exempt_note = models.CharField(max_length=300, blank=True, default="")
    updated_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(minimum_amount__gt=0), name="donation_settings_minimum_positive"),
        ]

    @classmethod
    def for_makerspace(cls, makerspace):
        return cls.objects.filter(makerspace=makerspace).first() or cls(makerspace=makerspace)
