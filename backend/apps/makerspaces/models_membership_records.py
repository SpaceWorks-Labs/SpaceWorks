"""Staff-side member record fields and display-only member titles (X13, X16).

`MembershipRecord` holds the record fields that are personal data -- the member's GSTIN
(L5 reads it, with `state_code`, for the place of supply) and the staff notes -- as
scoped PII on their own row, so the hot `MakerspaceMembership` model never carries the
encryption mixin. Staff notes are staff-only: never serialized to the member.

Titles ("Secretary", "Treasurer") are DISPLAY ONLY. They grant nothing: authority stays
in RBAC roles. One title per membership may be primary; the card prints that one (L3).
"""
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin
from apps.makerspaces.models_membership_rules import TITLE_COLOURS

GSTIN_PATTERN = re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
STATE_CODE_PATTERN = re.compile(r"^\d{2}$")


def validate_gstin(value):
    if value and not GSTIN_PATTERN.match(value):
        raise ValidationError("Enter a 15-character GSTIN, for example 29ABCDE1234F1Z5.")


def validate_state_code(value):
    if value and not STATE_CODE_PATTERN.match(value):
        raise ValidationError("Enter the two-digit state code, for example 29.")


class MembershipRecord(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    membership = models.OneToOneField(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE, related_name="record",
    )
    state_code = models.CharField(max_length=2, blank=True, default="", validators=[validate_state_code])
    # Envelopes are longer than the plaintext, so both are TextFields (max lengths live in
    # the encryption registry).
    gstin = models.TextField(blank=True, default="")
    staff_notes = models.TextField(blank=True, default="")
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="updated_membership_records",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        validate_gstin(self.gstin)
        validate_state_code(self.state_code)
        if self.gstin and self.state_code and self.gstin[:2] != self.state_code:
            raise ValidationError({"gstin": "The GSTIN's first two digits must match the state code."})


class MembershipTitle(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="membership_titles")
    name = models.CharField(max_length=60)
    colour = models.CharField(max_length=24, choices=TITLE_COLOURS, blank=True, default="")
    sort_order = models.PositiveIntegerField(default=0)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["makerspace_id", "sort_order", "name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "name"], name="uniq_membership_title_name"),
            models.CheckConstraint(condition=Q(colour__in=[key for key, _ in TITLE_COLOURS]),
                                   name="membership_title_brand_colour"),
        ]

    def __str__(self):
        return self.name


class MembershipTitleAssignment(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    membership = models.ForeignKey(
        "makerspaces.MakerspaceMembership", on_delete=models.CASCADE, related_name="title_assignments",
    )
    title = models.ForeignKey(MembershipTitle, on_delete=models.CASCADE, related_name="assignments")
    is_primary = models.BooleanField(default=False)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assigned_membership_titles",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "title__sort_order", "title__name", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["membership", "title"], name="uniq_membership_title_assignment"),
            models.UniqueConstraint(fields=["membership"], condition=Q(is_primary=True),
                                    name="uniq_membership_primary_title"),
        ]
