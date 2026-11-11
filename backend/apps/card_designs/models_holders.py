"""Rows that hang off ONE holder card of one of the three kinds (SPEC §4.1).

Every such row carries exactly one of `member_card`, `programme_card`, `event_card`, `staff_card`.
The two separable kinds are string references, nullable and tombstone-safe.
"""
from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin

HOLDER_FIELDS = ("member_card", "programme_card", "event_card", "staff_card")
HOLDER_KINDS = {field: field for field in HOLDER_FIELDS}


def exactly_one_holder(name):
    condition = None
    for chosen in HOLDER_FIELDS:
        clause = Q(**{f"{field}__isnull": field != chosen for field in HOLDER_FIELDS})
        condition = clause if condition is None else condition | clause
    return models.CheckConstraint(name=name, condition=condition)


def one_per_holder(prefix, condition=None):
    rows = []
    for field in HOLDER_FIELDS:
        clause = Q(**{f"{field}__isnull": False})
        if condition is not None:
            clause &= condition
        rows.append(models.UniqueConstraint(fields=[field], condition=clause, name=f"{prefix}_{field}"))
    return rows


class HolderCardMixin(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    member_card = models.ForeignKey("makerspaces.MemberCard", null=True, blank=True, on_delete=models.CASCADE,
                                    related_name="+")
    programme_card = models.ForeignKey("id_programmes.IdProgrammeCard", null=True, blank=True,
                                       on_delete=models.CASCADE, related_name="+")
    event_card = models.ForeignKey("events.EventIdCard", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name="+")
    # O-B4 part 2: staff ID cards (`models_staff_cards.StaffCard`).
    staff_card = models.ForeignKey("card_designs.StaffCard", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name="+")

    class Meta:
        abstract = True

    @property
    def holder_kind(self):
        for field in HOLDER_FIELDS:
            if getattr(self, f"{field}_id"):
                return field
        return ""

    @property
    def holder_id(self):
        return getattr(self, f"{self.holder_kind}_id") if self.holder_kind else None


class CardVerifyToken(HolderCardMixin):
    """The public check-link token. Never the desk QR payload; never logged (#71)."""
    class Retired(models.TextChoices):
        REISSUED = "reissued", gettext_noop("A newer card was issued")
        REVOKED = "revoked", "Revoked"
        ROTATED = "rotated", gettext_noop("Rotated by the holder")
        EXPIRED = "expired", "Expired"

    token = models.CharField(max_length=43, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_reason = models.CharField(max_length=12, choices=Retired.choices, blank=True, default="")

    class Meta:
        constraints = [exactly_one_holder("card_verify_token_one_holder"),
                       *one_per_holder("uniq_live_verify_token", Q(retired_at__isnull=True))]


class CardVerifyCheckDay(models.Model):
    """Aggregate public-check counter per space and day: no PII, never per-check audit."""
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    day = models.DateField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["makerspace", "day"], name="uniq_card_verify_day")]


class CardHolderExtras(ScopedPiiModelMixin, HolderCardMixin):
    """Opt-in sensitive extras (#132, Q-I5): holder and printed card only, encrypted."""
    blood_group = models.TextField(blank=True, default="")
    emergency_contact_name = models.TextField(blank=True, default="")
    emergency_contact_phone = models.TextField(blank=True, default="")
    consent_at = models.DateTimeField(null=True, blank=True)
    consent_version = models.CharField(max_length=16, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [exactly_one_holder("card_extras_one_holder"), *one_per_holder("uniq_card_extras")]


class CardPhotoRequest(HolderCardMixin):
    """A staff "photo needs update" request (#132, Q-I4): the card stays valid meanwhile."""
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name="+")
    reason = models.CharField(max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    reminded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [exactly_one_holder("card_photo_request_one_holder"),
                       *one_per_holder("uniq_open_photo_request", Q(resolved_at__isnull=True))]
