"""Membership plans and the dated terms a membership holds under them.

Forward plan phase 6 ("Membership plans and renewals"). Plans are OPTIONAL: a membership
with no term at all is a perfectly good membership, exactly as before this file existed.
A term is created when a join request is approved with a plan, or by staff. The renewal
task (`membership_plan_services.run_membership_renewals`) raises ONE charge inside the
renewal window when `payments.membership` is effectively on, and flips terms past
`ends_at` to `expired`; with the feature off the term simply expires and staff renew by
hand, dues out of band.

Expiry never touches `MakerspaceMembership.status` or `User.access_status`. The only
effect an expired term can have is the per-makerspace opt-in
`Makerspace.lapsed_members_cannot_borrow`, enforced by `request_access.require_current_term`
through the existing who-may-submit rule -- no new access state.

Release 2 (lane L4, decisions 69/71): a plan has a TYPE (rolling interval, ends at the
financial-year end, ends on one fixed date, or lifetime), separate new and renewal
prices, and per-plan overrides of the space's joining fee, rejoin rule, payment timing,
join mode and application form. A null override inherits the space default.
"""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.forms_schema.validation import validate_form_schema

from apps.makerspaces.models_membership_rules import JoinMode, LateRenewal, PaymentTiming, PlanType, RejoinRule


def default_renewal_reminders():
    return [14, 7, 1]


class MembershipPlan(models.Model):
    loan_max_active = models.PositiveIntegerField(null=True, blank=True)
    loan_max_items = models.PositiveIntegerField(null=True, blank=True)
    class Interval(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"
        CUSTOM_DAYS = "custom_days", "Custom number of days"

    PlanType = PlanType

    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="membership_plans"
    )
    name = models.CharField(max_length=120)
    interval = models.CharField(max_length=16, choices=Interval.choices)
    custom_days = models.PositiveIntegerField(null=True, blank=True)
    # The price a NEW member pays for a term.
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    # ISO 4217 lowercase, the way `payments.Payment.currency` stores it.
    currency = models.CharField(max_length=3, default="usd")
    is_active = models.BooleanField(default=True)
    auto_renew = models.BooleanField(default=False)
    renewal_open_days = models.PositiveSmallIntegerField(default=7, validators=[MaxValueValidator(365)])
    renewal_grace_days = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(365)])
    renewal_retries = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(3)])
    reminder_days_before = models.JSONField(default=default_renewal_reminders, blank=True)
    reminder_days_after = models.JSONField(default=list, blank=True)
    plan_type = models.CharField(max_length=16, choices=PlanType.choices, default=PlanType.ROLLING)
    fixed_end_date = models.DateField(null=True, blank=True)
    # Null renewal price = renewals cost the same as a new term.
    renewal_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    # Overrides of the space defaults; null inherits (decision 71).
    joining_fee = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)]
    )
    rejoin_rule = models.CharField(max_length=16, choices=RejoinRule.choices, null=True, blank=True)
    rejoin_after_days = models.PositiveIntegerField(null=True, blank=True, validators=[MaxValueValidator(3650)])
    payment_timing = models.CharField(max_length=24, choices=PaymentTiming.choices, null=True, blank=True)
    join_mode = models.CharField(max_length=16, choices=JoinMode.choices, null=True, blank=True)
    application_schema = models.JSONField(null=True, blank=True, default=None, validators=[validate_form_schema])
    late_renewal = models.CharField(max_length=16, choices=LateRenewal.choices, default=LateRenewal.BACKDATE)
    # Public listing (X5). A plan appears on public surfaces only when `is_public`,
    # active and not archived; prices are shown with it.
    slug = models.SlugField(max_length=80, blank=True, default="")
    description = models.TextField(blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    is_public = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["makerspace", "name"], name="uniq_membership_plan_name"
            ),
            models.UniqueConstraint(
                fields=["makerspace", "slug"], condition=~Q(slug=""), name="uniq_membership_plan_slug"
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="membership_plan_amount_non_negative"
            ),
            models.CheckConstraint(
                condition=Q(renewal_amount__isnull=True) | Q(renewal_amount__gte=0),
                name="membership_plan_renewal_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(joining_fee__isnull=True) | Q(joining_fee__gte=0),
                name="membership_plan_joining_fee_non_negative",
            ),
            # `custom_days` is meaningful for exactly one interval, and required there.
            models.CheckConstraint(
                condition=(
                    Q(interval="custom_days", custom_days__gt=0)
                    | (~Q(interval="custom_days") & Q(custom_days__isnull=True))
                ),
                name="membership_plan_custom_days_matches_interval",
            ),
            models.CheckConstraint(
                condition=Q(plan_type="fixed_end", fixed_end_date__isnull=False)
                | (~Q(plan_type="fixed_end") & Q(fixed_end_date__isnull=True)),
                name="membership_plan_fixed_end_matches_type",
            ),
            models.CheckConstraint(
                condition=Q(rejoin_rule="after_lapse", rejoin_after_days__gt=0)
                | (~Q(rejoin_rule="after_lapse") & Q(rejoin_after_days__isnull=True)),
                name="membership_plan_rejoin_days_matches_rule",
            ),
        ]
        ordering = ["makerspace_id", "sort_order", "name"]

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").lower()
        super().save(*args, **kwargs)

    @property
    def renewal_price(self):
        return self.amount if self.renewal_amount is None else self.renewal_amount

    @property
    def renews(self):
        """Whether a term under this plan can be followed by another one."""
        return self.plan_type in (PlanType.ROLLING, PlanType.FINANCIAL_YEAR)

    @property
    def listed(self):
        return self.is_public and self.is_active and self.archived_at is None

    def __str__(self):
        return f"{self.name} ({self.makerspace_id})"


from apps.makerspaces.models_membership_terms import MembershipTerm  # noqa: E402,F401
