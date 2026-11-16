"""Decision 223 (k), lane L3b: minors, guardian consent terms and the consent record.

* `MinorProfile` marks one account as a minor at one space. The minimum needed is stored: a date of
  birth OR an "under age" declaration. The birth date and the guardian's contact details are scoped PII
  (`encryption/registry_l3b.py`), so they are TextFields; the guardian may also be an account.
* `GuardianConsentTerms` is versioned exactly like `MakerspaceWaiver`: one active text per space, older
  versions kept so every consent can show the words that were signed.
* `GuardianConsent` is the e-signed record. Only its revocation ever changes; a purge removes it with
  the space.
"""
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_noop

from apps.encryption.mappers import ScopedPiiModelMixin


class GuardianConsentTerms(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="guardian_terms")
    body = models.TextField()
    version = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    superseded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["makerspace", "version"], name="guardian_terms_version_unique"),
            models.UniqueConstraint(fields=["makerspace"], condition=Q(is_active=True),
                                    name="guardian_terms_one_active"),
        ]


class MinorProfile(ScopedPiiModelMixin, models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="minor_profiles")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="minor_profiles")
    #: ISO `YYYY-MM-DD`, scoped PII; blank when staff only declared "under age".
    date_of_birth = models.TextField(blank=True, default="")
    declared_under_age = models.BooleanField(default=False)
    guardian_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="+")
    guardian_name = models.TextField(blank=True, default="")
    guardian_email = models.TextField(blank=True, default="")
    guardian_phone = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    cleared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        constraints = [models.UniqueConstraint(fields=["makerspace", "user"], name="minor_profile_one_per_space")]

    def __str__(self):
        return f"MinorProfile({self.makerspace_id}, {self.user_id})"


class GuardianConsent(ScopedPiiModelMixin, models.Model):
    class Method(models.TextChoices):
        GUARDIAN_ACCOUNT = "guardian_account", gettext_noop("Signed by the guardian in their own account")
        STAFF_RECORDED = "staff_recorded", gettext_noop("Signed on paper or at the desk and recorded by staff")

    profile = models.ForeignKey(MinorProfile, on_delete=models.CASCADE, related_name="consents")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    terms = models.ForeignKey(GuardianConsentTerms, on_delete=models.PROTECT, related_name="consents")
    terms_version = models.CharField(max_length=64)
    method = models.CharField(max_length=20, choices=Method.choices)
    #: The typed signature, scoped PII.
    signed_name = models.TextField()
    guardian_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name="+")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="+")
    signed_at = models.DateTimeField()
    valid_until = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="+")
    operation_id = models.CharField(max_length=64, null=True, blank=True)

    class Meta:
        ordering = ["-signed_at", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(valid_until__gt=models.F("signed_at")), name="guardian_consent_window"),
            models.UniqueConstraint(fields=["makerspace", "operation_id"], condition=Q(operation_id__isnull=False),
                                    name="guardian_consent_operation_unique"),
        ]
        indexes = [models.Index(fields=["profile", "valid_until"], name="guardian_consent_profile_idx")]

    def delete(self, *args, **kwargs):
        raise RuntimeError("A guardian consent is evidence and is removed only by a space purge.")
