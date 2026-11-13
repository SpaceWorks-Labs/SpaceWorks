"""Imported members waiting to accept (G18, owner decision #128 C-13).

An import never creates or links an account. Each accepted row becomes a
`ImportedMember` (a pending membership) bound to an emailed invitation (`MembershipRequest`, kind INVITE,
no user). The person accepts by signing in with that VERIFIED email; only then is a
membership activated, its imported term opened and its record fields copied. Staff may
instead keep a row as "record only": a register entry with no invite and no account.

Name, email, phone, GSTIN and notes are scoped PII (`encryption/registry_r2_l4.py`).
"""
from django.utils.translation import gettext_noop
from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.encryption.mappers import ScopedPiiModelMixin


class MembershipImportBatch(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="membership_import_batches")
    file_name = models.CharField(max_length=200, blank=True, default="")
    file_kind = models.CharField(max_length=8, choices=(("csv", "CSV"), ("xlsx", "Excel")), default="csv")
    # {"created": n, "updated": n, "skipped": n, "record_only": n, "invited": n}
    counts = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="membership_import_batches")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]


class ImportedMember(ScopedPiiModelMixin, models.Model):
    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        RECORD_ONLY = "record_only", gettext_noop("Record only")
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE,
                                   related_name="imported_members")
    batch = models.ForeignKey(MembershipImportBatch, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="rows")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.INVITED)
    name = models.TextField(blank=True, default="")
    email = models.TextField(blank=True, default="")
    phone = models.TextField(blank=True, default="")
    # The number the space used before (kept for reference; the gapless member number is
    # assigned on acceptance, X12).
    external_number = models.CharField(max_length=40, blank=True, default="")
    plan = models.ForeignKey("makerspaces.MembershipPlan", null=True, blank=True, on_delete=models.PROTECT,
                             related_name="imported_members")
    starts_on = models.DateField(null=True, blank=True)
    ends_on = models.DateField(null=True, blank=True)
    state_code = models.CharField(max_length=2, blank=True, default="")
    gstin = models.TextField(blank=True, default="")
    staff_notes = models.TextField(blank=True, default="")
    invitation = models.OneToOneField("makerspaces.MembershipRequest", null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="pending_import")
    membership = models.ForeignKey("makerspaces.MakerspaceMembership", null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="imported_from")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="created_imported_members")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(ends_on__isnull=True) | Q(starts_on__isnull=True)
                                   | Q(ends_on__gt=models.F("starts_on")),
                                   name="imported_member_dates_ordered"),
            models.UniqueConstraint(fields=["makerspace", "external_number"],
                                    condition=~Q(external_number="") & ~Q(status="cancelled"),
                                    name="uniq_imported_member_external_number"),
        ]
