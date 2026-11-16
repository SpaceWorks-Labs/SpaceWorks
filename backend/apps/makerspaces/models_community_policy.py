"""Decision 223 (k), lane L3b: the per-space settings of minors, volunteer credit and the join funnel.

One row per space, read with defaults when absent (reading never creates a row, the same contract as
`GuestPassPolicy` and `MakerspaceLoanPolicy`). Every value is a Space Manager decision
(`manage_makerspace`, audited with field names) and every feature it configures is gated by its own
capability, so these columns are inert while the capability is off.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.translation import gettext_noop
from apps.payments.money_model import MoneyDecimalField


class CommunityPolicy(models.Model):
    class CreditKind(models.TextChoices):
        DISCOUNT = "discount", gettext_noop("A discount amount")
        FREE_DAYS = "free_days", gettext_noop("Free days on the next term")

    makerspace = models.OneToOneField(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="community_policy",
    )
    # -- minors (capability `membership.minors`) ------------------------------------------------
    minors_admitted = models.BooleanField(default=False)
    minors_minimum_age = models.PositiveSmallIntegerField(default=13, validators=[MaxValueValidator(17)])
    adult_age = models.PositiveSmallIntegerField(
        default=18, validators=[MinValueValidator(16), MaxValueValidator(21)])
    guardian_must_be_present = models.BooleanField(default=True)
    minors_may_borrow = models.BooleanField(default=False)
    minors_may_use_machines = models.BooleanField(default=False)
    consent_valid_days = models.PositiveIntegerField(
        default=365, validators=[MinValueValidator(1), MaxValueValidator(1825)])
    # -- volunteer credit (capability `membership.volunteer_credit`) ----------------------------
    #: Approved minutes that earn one credit; 0 keeps hours logged but converts nothing.
    volunteer_minutes_per_credit = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(100000)])
    volunteer_credit_kind = models.CharField(max_length=12, choices=CreditKind.choices, default=CreditKind.DISCOUNT)
    volunteer_credit_amount = MoneyDecimalField(
        max_digits=11, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    volunteer_credit_days = models.PositiveIntegerField(default=0, validators=[MaxValueValidator(366)])
    # -- join funnel (capability `membership.join_funnel`) --------------------------------------
    join_followup_enabled = models.BooleanField(default=False)
    join_followup_delay_hours = models.PositiveIntegerField(
        default=24, validators=[MinValueValidator(1), MaxValueValidator(336)])
    updated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def for_makerspace(cls, makerspace):
        return cls.objects.filter(makerspace=makerspace).first() or cls(makerspace=makerspace)
