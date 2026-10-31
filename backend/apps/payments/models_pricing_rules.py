"""Member discounts and loan fee waivers (lane L15, decisions #84/#85 A3/A4/A14).

* `PriceDiscount` -- an automatic discount for all members, the members on one plan, or
  one member. Only the single best one applies to a quote (then an event promo code on
  top). Archived, never deleted: a frozen quote names the rule it used.
* `LoanFeeWaiver` -- staff make a loan's fees free, all of them or the named ones, with a
  required reason. Append-only: the model refuses update and delete and a Postgres
  trigger backs it. A waiver is undone only by a NEW row that `revokes` it (the amends
  pattern), which affects only charges not yet raised. The refundable deposit is never
  waivable: it has its own release path.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q


class PriceDiscount(models.Model):
    class Audience(models.TextChoices):
        ALL_MEMBERS = "all_members", "All members"
        PLAN = "plan", "Members on a plan"
        MEMBER = "member", "One member"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="price_discounts")
    #: Staff-authored and shown to members on their quote. Never a person's name.
    name = models.CharField(max_length=120)
    audience = models.CharField(max_length=16, choices=Audience.choices)
    #: SET_NULL: purging the membership module deletes plans; a plan rule whose plan is
    #: gone matches nobody and stays as the record a frozen quote names.
    plan = models.ForeignKey("makerspaces.MembershipPlan", null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="price_discounts")
    member = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT,
                               related_name="price_discounts")
    #: Pricing domains it applies to; empty means every domain.
    domains = models.JSONField(default=list, blank=True)
    #: Components it applies to; empty means each domain's discountable components. Naming
    #: a deposit, late, damage or lost component is the only way a discount reaches one.
    components = models.JSONField(default=list, blank=True)
    percent_bps = models.PositiveIntegerField(null=True, blank=True,
                                              validators=[MinValueValidator(1), MaxValueValidator(10000)])
    amount_off = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(percent_bps__isnull=False, amount_off__isnull=True)
                           | Q(percent_bps__isnull=True, amount_off__isnull=False)),
                name="price_discount_one_kind"),
            models.CheckConstraint(condition=Q(percent_bps__isnull=True) | Q(percent_bps__gte=1, percent_bps__lte=10000),
                                   name="price_discount_percent_range"),
            models.CheckConstraint(condition=Q(amount_off__isnull=True) | Q(amount_off__gt=0),
                                   name="price_discount_amount_positive"),
            models.CheckConstraint(
                condition=(Q(audience="all_members", plan__isnull=True, member__isnull=True)
                           | Q(audience="plan", member__isnull=True)
                           | Q(audience="member", plan__isnull=True, member__isnull=False)),
                name="price_discount_audience_target"),
            models.CheckConstraint(condition=Q(starts_at__isnull=True) | Q(ends_at__isnull=True)
                                   | Q(ends_at__gt=models.F("starts_at")), name="price_discount_window_ordered"),
        ]
        indexes = [models.Index(fields=["makerspace", "is_active"], name="price_discount_active_idx")]

    def clean(self):
        if self.audience == self.Audience.PLAN and self.plan_id is None:
            raise ValidationError({"plan": "Choose the plan whose members get this discount."})
        if self.plan_id and self.plan.makerspace_id != self.makerspace_id:
            raise ValidationError({"plan": "The plan must belong to this makerspace."})

    def delete(self, *args, **kwargs):
        raise ValidationError("Discounts are archived, never deleted.")

    def __str__(self):
        return f"Discount {self.name} ({self.audience}) for makerspace {self.makerspace_id}"


class LoanFeeWaiver(models.Model):
    class Component(models.TextChoices):
        RENTAL = "rental", "Rental"
        LATE = "late", "Late fee"
        DAMAGE = "damage", "Damage"
        LOST = "lost", "Lost item"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.PROTECT, related_name="+")
    request = models.ForeignKey("hardware_requests.HardwareRequest", on_delete=models.PROTECT,
                                related_name="fee_waivers")
    #: Waived components; an empty list means every loan fee (never the deposit).
    components = models.JSONField(default=list, blank=True)
    #: Staff-authored financial context, required. Shown in the loan's charge history.
    reason = models.CharField(max_length=500)
    #: Set on a revocation row: the waiver it undoes (one revocation per waiver).
    revokes = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT,
                                   related_name="revocation")
    created_by = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["request_id", "created_at", "pk"]
        constraints = [
            models.CheckConstraint(condition=~Q(reason=""), name="loan_fee_waiver_reason_required"),
        ]

    @property
    def is_revocation(self):
        return self.revokes_id is not None

    def covered(self):
        """The components this waiver makes free."""
        return frozenset(self.components or self.Component.values)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("Loan fee waivers are append-only.")
        if not (self.reason or "").strip():
            raise ValidationError({"reason": "A reason is required."})
        unknown = set(self.components or ()) - set(self.Component.values)
        if unknown:
            raise ValidationError({"components": f"Unknown loan fee components: {sorted(unknown)}."})
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Loan fee waivers are append-only.")
