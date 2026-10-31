"""A member's consent ledger and per-space erasure requests (X10, X29).

Consent: one row per purpose the member agreed to, at the privacy-notice version the
space published when they agreed. Withdrawing stamps `withdrawn_at` on that row; agreeing
again later opens a NEW row, so the ledger shows every given/withdrawn period. There are
no guardian or minor fields (owner decision 3).

Erasure: the member asks one space to anonymise what it holds about their membership.
Staff approve (anonymise that space's membership data; money rows and the audit log are
kept) or reject with a note. Never deletes the account -- account deletion is separate.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin


class MembershipConsent(models.Model):
    class Source(models.TextChoices):
        MEMBER = "member", "Given by the member"
        JOIN = "join", "Given when joining"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE, related_name="consents",
    )
    purpose = models.CharField(max_length=64)
    notice_version = models.CharField(max_length=64, blank=True, default="")
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MEMBER)
    given_at = models.DateTimeField()
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["purpose", "-given_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["membership", "purpose"], condition=Q(withdrawn_at__isnull=True),
                                    name="uniq_membership_consent_open_purpose"),
            models.CheckConstraint(condition=Q(withdrawn_at__isnull=True) | Q(withdrawn_at__gte=models.F("given_at")),
                                   name="membership_consent_withdrawn_after_given"),
        ]


class MembershipErasureRequest(ScopedPiiModelMixin, models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE, related_name="erasure_requests",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.REQUESTED)
    # The member's own words (scoped PII); cleared when the erasure is carried out.
    member_note = models.TextField(blank=True, default="")
    # Staff-authored and shown to the member.
    decision_note = models.CharField(max_length=500, blank=True, default="")
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="decided_membership_erasures",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.UniqueConstraint(fields=["membership"], condition=Q(status="requested"),
                                    name="uniq_membership_open_erasure"),
        ]
