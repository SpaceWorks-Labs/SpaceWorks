"""Admission policy and the append-only accountability behind a vouch."""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.forms_schema.validation import validate_form_schema
from apps.makerspaces.models_membership_rules import JoinMode, PaymentTiming, RejoinRule


class MakerspaceMembershipSettings(models.Model):
    JoinMode = JoinMode
    PaymentTiming = PaymentTiming
    RejoinRule = RejoinRule

    makerspace = models.OneToOneField(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="admission_settings"
    )
    # Until a manager opts in, the legacy columns remain authoritative aliases.
    configured = models.BooleanField(default=False)
    join_mode = models.CharField(max_length=16, choices=JoinMode.choices, default=JoinMode.APPROVAL)
    vouches_required = models.PositiveSmallIntegerField(default=1)
    voucher_min_tenure_days = models.PositiveIntegerField(default=30)
    voucher_pending_limit = models.PositiveSmallIntegerField(default=3)
    vouch_expiry_days = models.PositiveIntegerField(default=30)
    vouch_replaces_approval = models.BooleanField(default=False)
    payment_timing = models.CharField(max_length=24, choices=PaymentTiming.choices, default=PaymentTiming.AFTER)
    application_schema = models.JSONField(null=True, blank=True, default=None, validators=[validate_form_schema])
    default_plan = models.ForeignKey(
        "makerspaces.MembershipPlan", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="default_for_admissions",
    )
    joining_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    joining_fee_currency = models.CharField(max_length=3, default="usd")
    rejoin_dues_rule = models.CharField(max_length=16, choices=RejoinRule.choices, default=RejoinRule.ONCE)
    request_expiry_days = models.PositiveIntegerField(default=30)
    rejoin_after_days = models.PositiveIntegerField(null=True, blank=True)
    # How the fixed member number is printed (X12, decisions 71 and #128 C-29), e.g.
    # "TNK-{number:4}" -> TNK-0042. Tokens: {number} / {number:N} (zero-padded to N) and
    # {year} (the year the person first joined). Validated by `membership_number`.
    member_number_pattern = models.CharField(max_length=40, blank=True, default="")
    # Consent ledger (X10): the published privacy-notice version and the purposes a member
    # may agree to, as [{"key", "label", "description"}]. Empty = no consent questions.
    privacy_notice_version = models.CharField(max_length=64, blank=True, default="")
    consent_purposes = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(joining_fee__gte=0), name="admission_fee_nonnegative"),
            models.CheckConstraint(condition=Q(vouches_required__gte=1, vouches_required__lte=5), name="admission_vouch_count_range"),
            models.CheckConstraint(condition=Q(voucher_pending_limit__gte=1), name="admission_voucher_limit_positive"),
            models.CheckConstraint(condition=Q(vouch_expiry_days__gte=1, request_expiry_days__gte=1), name="admission_expiry_positive"),
            models.CheckConstraint(
                condition=Q(rejoin_dues_rule="after_lapse", rejoin_after_days__gt=0)
                | (~Q(rejoin_dues_rule="after_lapse") & Q(rejoin_after_days__isnull=True)),
                name="admission_rejoin_days_matches_rule",
            ),
        ]


class MembershipVouch(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    request = models.ForeignKey("makerspaces.MembershipRequest", on_delete=models.CASCADE, related_name="vouches")
    voucher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="membership_vouches")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["created_at", "pk"]
        constraints = [models.UniqueConstraint(fields=["request", "voucher"], name="uniq_membership_request_voucher")]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Membership vouches are immutable.")
        if self.request.makerspace_id != self.makerspace_id:
            raise ValueError("Vouch and request must belong to the same makerspace.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Membership vouches are immutable.")
