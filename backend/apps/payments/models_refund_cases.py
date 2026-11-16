"""Refund cases and refund policies: an ENTITLEMENT to money back, never money itself.

A `RefundCase` records that a member may be owed money on a settled charge -- because
the space's cancellation policy says so (`kind=due`) or because the member asked
(`kind=request`). It moves no money. Only a staff approval creates a `Refund` ledger
line, under the Payment row lock, so money never leaves without a human decision.

Why not a PENDING `Refund` row instead: pending refunds count against the refundable
balance, are settled by provider webhooks and block account deletion. An entitlement
that nobody has approved must do none of those things.

`RefundPolicy` is one row per (makerspace, area). With no row the computed due is zero
and staff decide case by case. An event may carry its own override (lane L6, #69/#71), read
through `refund_policy.area_policy`; after its first sale it may only become more generous.
"""

from django.utils.translation import gettext_noop
from django.core.validators import MaxValueValidator
from django.db import models

from apps.payments.models_payment import Payment
from apps.payments.models_refund import Refund
from apps.payments.money_model import MoneyDecimalField


class RefundCase(models.Model):
    class Kind(models.TextChoices):
        DUE = "due", gettext_noop("Due under policy")
        REQUEST = "request", gettext_noop("Requested by member")

    class Area(models.TextChoices):
        # Mirrors `payments.availability.SUBJECT_DOMAINS` values (R8).
        MACHINES = "machines", "Machines"
        BOOKINGS = "bookings", "Bookings"
        EVENTS = "events", "Events"
        MEMBERSHIP = "membership", "Membership"
        LOANS = "loans", "Loans"
        #: Lane L18: donations and sponsorship money (#59: refunds only through a case).
        DONATIONS = "donations", "Donations"
        #: Lane L22: shop orders (returns, uncollected and unfilled orders).
        SHOP = "shop", "Shop"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        APPROVED = "approved", "Approved"
        #: The provider refused the approved refund. Staff retry or decline (R2).
        APPROVAL_FAILED = "approval_failed", gettext_noop("Approval failed")
        DECLINED = "declined", "Declined"
        WITHDRAWN = "withdrawn", "Withdrawn"
        #: Closed by the system: nothing left to refund, or the charge was refunded
        #: outside the case (R7).
        VOID = "void", "Void"

    #: Statuses that still await a staff decision. One per payment (R1).
    ACTIVE_STATUSES = (Status.OPEN, Status.APPROVAL_FAILED)

    class ReasonCode(models.TextChoices):
        EVENT_CANCELLED = "event_cancelled", gettext_noop("Event cancelled by the space")
        REGISTRATION_CANCELLED = "registration_cancelled", gettext_noop("Registration cancelled")
        BOOKING_CANCELLED = "booking_cancelled", gettext_noop("Booking cancelled")
        #: Staff cancelled a member's booking: owed in full (decision 72).
        STAFF_CANCELLED = "staff_cancelled", gettext_noop("Cancelled by staff")
        MEMBERSHIP_CANCELLED = "membership_cancelled", gettext_noop("Membership term cancelled")
        MEMBER_REQUEST = "member_request", gettext_noop("Member request")
        #: Staff opened it for an unexpected online capture (lane L5 capture flags).
        CAPTURE_FLAGGED = "capture_flagged", gettext_noop("Unexpected online capture")
        #: Staff waived a loan fee the member had already paid (lane L15, A14).
        FEE_WAIVED = "fee_waived", gettext_noop("Loan fee waived by staff")
        #: Lane L6: a paid order that could not be seated, a cheaper ticket type, and a
        #: series-pass occurrence the space cancelled (the organiser's partial amount).
        ORDER_UNFULFILLED = "order_unfulfilled", gettext_noop("Order could not be seated")
        TICKET_TYPE_CHANGED = "ticket_type_changed", gettext_noop("Changed to a cheaper ticket")
        PASS_OCCURRENCE_CANCELLED = "pass_occurrence_cancelled", gettext_noop("Pass occurrence cancelled")
        #: Lane L18: staff opened a case to return a gift or a sponsor's payment.
        DONATION_RETURNED = "donation_returned", gettext_noop("Gift returned to the giver")
        #: Lane L21b (#59): a paid project disqualified with "refund on disqualification" set, and a
        #: rejected or closed paid team. Each opens a DUE case for the full amount; staff decide.
        SUBMISSION_DISQUALIFIED = "submission_disqualified", gettext_noop("Project disqualified")
        TEAM_REJECTED = "team_rejected", gettext_noop("Team rejected")
        #: Lane L24: a price LOWERED after payment (#163A), a member cancelling a prepaid
        #: machine job before it starts (#171 (2)), and a prepaid job whose actual cost came
        #: in below its quote (#171 (3)). Each case still needs a staff approval.
        PRICE_DROP = "price_drop", gettext_noop("Price lowered after payment")
        JOB_CANCELLED = "job_cancelled", gettext_noop("Prepaid job cancelled before it started")
        QUOTE_DIFFERENCE = "quote_difference", gettext_noop("Actual cost below the prepaid quote")
        #: Lane L22: shop items taken back, a paid order nobody collected, a paid order the
        #: stock could not fill.
        SHOP_RETURN = "shop_return", gettext_noop("Shop items returned")
        SHOP_UNCOLLECTED = "shop_uncollected", gettext_noop("Shop order not collected")
        SHOP_UNFULFILLED = "shop_unfulfilled", gettext_noop("Shop order could not be filled")
        #: Hack-money G2: a paid entry fee of a withdrawn project, or of a team that did not advance
        #: at a published shortlist, each behind its own per-event switch (off by default).
        SUBMISSION_WITHDRAWN = "submission_withdrawn", gettext_noop("Project withdrawn")
        NOT_SHORTLISTED = "not_shortlisted", gettext_noop("Team not shortlisted")
        # Hack-money G10: a staff-approved deposit settlement returns an attendee's deposit.
        DEPOSIT_RETURNED = "deposit_returned", gettext_noop("Deposit returned after the event")

    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="refund_cases")
    kind = models.CharField(max_length=16, choices=Kind.choices)
    area = models.CharField(max_length=16, choices=Area.choices)
    reason_code = models.CharField(max_length=32, choices=ReasonCode.choices)
    # The member's own words. Shown to staff deciding the case and back to the member;
    # never copied into audit meta.
    member_reason = models.CharField(max_length=500, blank=True, default="")
    #: What the policy says is owed when the case opened or was upgraded. Staff may
    #: approve a different amount; the approval re-clamps to the live balance.
    due_amount = MoneyDecimalField(max_digits=13, decimal_places=3, default=0)
    #: The policy figures used to compute `due_amount`, frozen for the receipt trail.
    policy_snapshot = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    #: The latest refund attempt an approval created. An FK, not 1:1 -- a failed provider
    #: attempt is retried with a fresh Refund row (R2).
    refund = models.ForeignKey(
        Refund, null=True, blank=True, on_delete=models.PROTECT, related_name="refund_cases",
    )
    approved_amount = MoneyDecimalField(max_digits=13, decimal_places=3, null=True, blank=True)
    # Staff-authored and shown to the member. Financial context only, never PII.
    decision_note = models.CharField(max_length=500, blank=True, default="")
    requested_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="requested_refund_cases",
    )
    decided_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="decided_refund_cases",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["payment"], condition=models.Q(status__in=["open", "approval_failed"]),
                name="refund_case_one_active_per_payment",
            ),
            models.UniqueConstraint(
                fields=["payment"], condition=models.Q(kind="due"), name="refund_case_one_due_per_payment",
            ),
            models.CheckConstraint(condition=models.Q(due_amount__gte=0), name="refund_case_due_not_negative"),
            models.CheckConstraint(
                condition=models.Q(approved_amount__isnull=True) | models.Q(approved_amount__gt=0),
                name="refund_case_approved_positive",
            ),
        ]
        indexes = [models.Index(fields=["status", "area"], name="refund_case_status_area")]

    def __str__(self):
        return f"Refund case {self.pk} ({self.status}) on payment {self.payment_id}"


class RefundPolicy(models.Model):
    class Area(models.TextChoices):
        EVENTS = "events", "Events"
        BOOKINGS = "bookings", "Bookings"
        # Owner decision 68: a paid membership TERM has a policy too, optionally per plan.
        MEMBERSHIP = "membership", "Memberships"

    class PartialMode(models.TextChoices):
        PERCENT = "percent", gettext_noop("A fixed percentage")
        #: Memberships only: the unused share of the term, by time.
        PRO_RATA = "pro_rata", gettext_noop("Pro rata of unused term time")

    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="refund_policies",
    )
    area = models.CharField(max_length=16, choices=Area.choices)
    #: Memberships only: a rule for one plan. Null is the area default every plan falls back to.
    plan = models.ForeignKey(
        "makerspaces.MembershipPlan", null=True, blank=True, on_delete=models.CASCADE,
        related_name="refund_policies",
    )
    #: Cancelling at least this many minutes before the start refunds the full amount.
    full_before_minutes = models.PositiveIntegerField(default=0)
    #: At least this many minutes before (but under the full window) refunds a percentage.
    partial_before_minutes = models.PositiveIntegerField(default=0)
    partial_percent = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    #: Memberships only: cancelling within this many days of the term start refunds in full.
    full_within_days = models.PositiveIntegerField(default=0)
    #: Memberships choose pro rata or a percentage after the full window; others use a percentage.
    partial_mode = models.CharField(max_length=16, choices=PartialMode.choices, default=PartialMode.PERCENT)
    #: Kept by the space on every refund, in the space's default currency.
    cancellation_fee = MoneyDecimalField(max_digits=13, decimal_places=3, default=0)
    updated_by = models.ForeignKey(
        "accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "area"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "area"], condition=models.Q(plan__isnull=True),
                                    name="refund_policy_one_per_area"),
            models.UniqueConstraint(fields=["makerspace", "area", "plan"], condition=models.Q(plan__isnull=False),
                                    name="refund_policy_one_per_plan"),
            models.CheckConstraint(condition=models.Q(plan__isnull=True) | models.Q(area="membership"),
                                   name="refund_policy_plan_is_membership"),
            models.CheckConstraint(condition=models.Q(partial_mode="percent") | models.Q(area="membership"),
                                   name="refund_policy_pro_rata_is_membership"),
            models.CheckConstraint(
                condition=models.Q(full_before_minutes__gte=models.F("partial_before_minutes")),
                name="refund_policy_windows_ordered",
            ),
            models.CheckConstraint(condition=models.Q(partial_percent__lte=100), name="refund_policy_percent_range"),
            models.CheckConstraint(condition=models.Q(cancellation_fee__gte=0), name="refund_policy_fee_not_negative"),
        ]

    def __str__(self):
        return f"Refund policy {self.area} (plan {self.plan_id}) for makerspace {self.makerspace_id}"
