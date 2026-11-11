"""Decision 223: guest passes, day-pass products and the per-space guest policy.

A guest pass is a dated permit held by an EXISTING account (a person or a walk-in `User`).
It is never a `MakerspaceMembership`: it is not counted on the roster or in member reports,
it earns no member card, and it unlocks only what its frozen `entitlements` snapshot says
while `valid_from <= now < valid_until`.

Mutability. A pass is accountability evidence, so only its status, its waiver stamp, its
revocation fields and `converted_membership` ever change; it is never deleted by a request
path (a module purge or a tenant purge removes it with the space). Services enforce the
transitions; the constraints below make the shape unrepresentable when they are bypassed.
"""

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext, gettext_noop
from apps.payments.money_model import MoneyDecimalField


class GuestPassPolicy(models.Model):
    """One row per space: every "Space Manager decides" setting of decision 223 and its default."""

    class Borrowing(models.TextChoices):
        NONE = "none", gettext_noop("No borrowing")
        ON_SITE = "on_site", gettext_noop("On site only, due by the end of the pass")
        FULL = "full_with_deposit", gettext_noop("Full borrowing with a mandatory deposit")

    class Machines(models.TextChoices):
        NONE = "none", gettext_noop("No machine use")
        SUPERVISED = "supervised", gettext_noop("Supervised use in an instructor's session")
        AFTER_CERT = "after_induction_cert", gettext_noop("After a certification from an induction event")

    class Liability(models.TextChoices):
        GUEST = "guest", gettext_noop("The guest is the accountable borrower")
        SPONSOR = "sponsor", gettext_noop("The sponsor pays")

    class WalkIn(models.TextChoices):
        GUEST_PASS = "guest_pass", gettext_noop("A guest pass")
        MEMBERSHIP = "membership", gettext_noop("A full membership")

    makerspace = models.OneToOneField(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="guest_pass_policy",
    )
    guest_borrowing_mode = models.CharField(max_length=24, choices=Borrowing.choices, default=Borrowing.ON_SITE)
    guest_machine_mode = models.CharField(max_length=24, choices=Machines.choices, default=Machines.NONE)
    sponsored_liability = models.CharField(max_length=16, choices=Liability.choices, default=Liability.GUEST)
    walk_in_registration_creates = models.CharField(max_length=16, choices=WalkIn.choices, default=WalkIn.GUEST_PASS)
    waiver_required_on_site = models.BooleanField(default=True)
    #: Open item B12: keep the on-site waiver gate for non-members even after guest passes are switched
    #: off (presence self check-in). Edited while passes are on; stays in force when they are turned off.
    waiver_gate_without_passes = models.BooleanField(default=False)
    sponsor_min_tenure_days = models.PositiveIntegerField(default=30, validators=[MaxValueValidator(3650)])
    max_concurrent_guests_per_sponsor = models.PositiveIntegerField(
        default=2, validators=[MinValueValidator(1), MaxValueValidator(50)],
    )
    sponsor_must_be_present = models.BooleanField(default=True)
    #: Passes plus guest presence sessions in a rolling 30 days that raise the join prompt (soft).
    visits_before_join_prompt = models.PositiveIntegerField(default=4, validators=[MinValueValidator(1)])
    #: Optional hard stop: at or above this many visits in 30 days no new pass is issued. Null = off.
    hard_visit_cap = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    #: Space-wide cap on day passes sold per local day. Null = unlimited.
    day_pass_daily_cap = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    updated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def for_makerspace(cls, makerspace):
        """Reading defaults never creates a row (the same contract as `MakerspaceLoanPolicy`)."""
        return cls.objects.filter(makerspace=makerspace).first() or cls(makerspace=makerspace)


class DayPassProduct(models.Model):
    """A priced day pass a space sells. Archived, never deleted, once a pass was sold from it."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="day_pass_products")
    name = models.CharField(max_length=120)
    amount = MoneyDecimalField(max_digits=11, decimal_places=3, default=0, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, blank=True, default="")
    #: Template for the pass's frozen entitlements; the space policy fills any key left out.
    entitlements = models.JSONField(default=dict, blank=True)
    daily_cap = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    is_public = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        indexes = [models.Index(fields=["makerspace", "is_active"], name="daypass_space_active_idx")]

    def __str__(self):
        return f"{self.name} ({self.makerspace_id})"


class GuestPass(models.Model):
    class Kind(models.TextChoices):
        EVENT = "event", gettext_noop("Event guest")
        SPONSORED = "sponsored", gettext_noop("Sponsored guest")
        DAY = "day", gettext_noop("Day pass")

    class Status(models.TextChoices):
        ISSUED = "issued", gettext_noop("Issued")
        ACTIVE = "active", gettext_noop("Active")
        EXPIRED = "expired", gettext_noop("Expired")
        REVOKED = "revoked", gettext_noop("Revoked")
        CONVERTED = "converted", gettext_noop("Converted to membership")

    #: Statuses that still occupy the holder's one-pass-per-day slot and the sponsor's guest limit.
    LIVE_STATUSES = ("issued", "active")

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="guest_passes")
    holder = models.ForeignKey("accounts.User", on_delete=models.PROTECT, related_name="guest_passes")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ISSUED)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    #: The makerspace-local calendar day of `valid_from`; carries the one-pass-per-day rule.
    pass_date = models.DateField()
    sponsor = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="sponsored_guest_passes",
    )
    sponsor_membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    product = models.ForeignKey(
        "makerspaces.DayPassProduct", null=True, blank=True, on_delete=models.PROTECT, related_name="passes",
    )
    #: Frozen at issue: `{"presence": bool, "borrow": "none"|"on_site"|"full_with_deposit",
    #: "machines": "none"|"supervised"|"after_induction_cert"}`. Later policy edits never rewrite a live pass.
    entitlements = models.JSONField(default=dict)
    accepted_waiver = models.ForeignKey(
        "makerspaces.MakerspaceWaiver", null=True, blank=True, on_delete=models.PROTECT, related_name="+",
    )
    waiver_version = models.CharField(max_length=64, null=True, blank=True)
    waiver_accepted_at = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    revoked_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=255, blank=True, default="")
    converted_membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    #: Idempotent retries: the same operation id in the same space returns the same pass.
    operation_id = models.CharField(max_length=64, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-valid_from", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(valid_until__gt=models.F("valid_from")), name="guest_pass_window_ordered"),
            models.CheckConstraint(
                condition=(Q(accepted_waiver__isnull=True, waiver_version__isnull=True, waiver_accepted_at__isnull=True)
                           | Q(accepted_waiver__isnull=False, waiver_version__isnull=False,
                               waiver_accepted_at__isnull=False)),
                name="guest_pass_waiver_all_or_none",
            ),
            # One live pass per holder per space per local day (decision 223 limits).
            models.UniqueConstraint(
                fields=["makerspace", "holder", "pass_date"], condition=Q(status__in=["issued", "active"]),
                name="guest_pass_one_live_per_holder_day",
            ),
            models.UniqueConstraint(
                fields=["makerspace", "operation_id"], condition=Q(operation_id__isnull=False),
                name="guest_pass_operation_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["makerspace", "holder", "valid_until"], name="guest_pass_holder_idx"),
            models.Index(fields=["makerspace", "sponsor", "status"], name="guest_pass_sponsor_idx"),
        ]

    def __str__(self):
        return f"GuestPass({self.kind}, {self.makerspace_id}, {self.holder_id})"

    def clean(self):
        if self.makerspace_id and self.accepted_waiver_id and self.accepted_waiver.makerspace_id != self.makerspace_id:
            raise ValidationError({"accepted_waiver": gettext("Waiver must belong to the same makerspace.")})
        if self.makerspace_id and self.product_id and self.product.makerspace_id != self.makerspace_id:
            raise ValidationError({"product": gettext("Product must belong to the same makerspace.")})

    def delete(self, *args, **kwargs):
        raise RuntimeError("GuestPass rows are accountability evidence and are removed only by a space purge.")
