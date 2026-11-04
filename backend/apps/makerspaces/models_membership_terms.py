"""A membership's dated terms, what each one was sold for, and its standing history.

A term freezes the price, joining fee, currency and plan type it was opened with (X6),
so a later plan edit never rewrites what a member bought. `kind` says whether it was a
first term, a renewal or a reinstatement after a gap (X7).

`MembershipTermStatusEvent` is APPEND-ONLY: one row per standing change, carrying both
when the change took effect in the membership's own timeline (`effective_at`) and when
the system recorded it (`recorded_at`). A backdated renewal is recorded today but
effective at the old end, so reports can rebuild the standing a member had on any date.
"""
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from apps.makerspaces.models_membership_rules import PlanType, TermKind, TermStanding

#: The end instant stored for a lifetime term. Far enough out that no interval reaches it,
#: early enough that converting it to any local time zone cannot overflow `datetime`.
LIFETIME_ENDS_AT = datetime(9000, 1, 1, tzinfo=dt_timezone.utc)


class MembershipTerm(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    Kind = TermKind

    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE, related_name="terms"
    )
    # PROTECT: a term is the record of what a member was sold; deleting the plan under it
    # would erase the price history behind a real charge. Deactivate plans instead.
    plan = models.ForeignKey("makerspaces.MembershipPlan", on_delete=models.PROTECT, related_name="terms")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    # The ONE renewal charge raised for this term. Money is never deleted, so SET_NULL is
    # only ever reached by the payments purge path; the Payment row itself stays.
    renewal_payment = models.ForeignKey(
        "payments.Payment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="renewed_membership_terms",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_membership_terms",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    renewed_from = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="next_term",
    )
    renewal_attempts = models.PositiveSmallIntegerField(default=0)
    renewal_retry_at = models.DateTimeField(null=True, blank=True)
    grace_until = models.DateTimeField(null=True, blank=True)
    kind = models.CharField(max_length=16, choices=TermKind.choices, default=TermKind.NEW)
    # Frozen at opening (X6). A null price is a term opened before release 2.
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    joining_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, blank=True, default="")
    plan_type = models.CharField(max_length=16, choices=PlanType.choices, default=PlanType.ROLLING)
    # The join request whose admission charge paid for this (first) term, if any. The
    # refund policy reads it to assess that charge against the term it bought (#68).
    admission_request = models.ForeignKey(
        "makerspaces.MembershipRequest", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="admitted_terms",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="membership_term_ends_after_start"
            ),
            models.CheckConstraint(
                condition=(Q(price__isnull=True) | Q(price__gte=0)) & Q(joining_fee__gte=0),
                name="membership_term_snapshot_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "ends_at"], name="membershipterm_status_ends_idx"),
        ]
        ordering = ["-starts_at", "-pk"]

    @property
    def is_lifetime(self):
        return self.plan_type == PlanType.LIFETIME or self.ends_at >= LIFETIME_ENDS_AT

    def __str__(self):
        return f"term {self.pk} of membership {self.membership_id}"


class MembershipTermStatusEvent(models.Model):
    """One standing change of one term. Never updated, never deleted (except by purge)."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE, related_name="term_events",
    )
    term = models.ForeignKey(MembershipTerm, on_delete=models.CASCADE, related_name="status_events")
    status = models.CharField(max_length=16, choices=TermStanding.choices)
    effective_at = models.DateTimeField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    # The term's end after this change (an extension moves it; lifetime is the sentinel).
    ends_at = models.DateTimeField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="membership_term_events",
    )
    # Staff-authored context (an extension reason, a refund that ended the term).
    reason = models.CharField(max_length=500, blank=True, default="")

    class Meta:
        ordering = ["effective_at", "pk"]
        indexes = [models.Index(fields=["makerspace", "effective_at"], name="term_event_space_effective")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Membership term history is append-only.")
        if self.term_id and self.membership_id and self.term.membership_id != self.membership_id:
            raise ValueError("Term history must belong to the term's membership.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Membership term history is append-only.")
