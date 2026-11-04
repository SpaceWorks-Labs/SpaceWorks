"""Shared credential fields only; concrete domain models own typed targets/tables."""

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def invite_expiry():
    return timezone.now() + timedelta(days=7)


def validate_permission_set(value, vocabulary):
    if (
        not isinstance(value, list) or not value
        or any(not isinstance(item, str) or item not in vocabulary for item in value)
        or len(value) != len(set(value))
    ):
        raise ValidationError("Choose a nonempty list of distinct resource permissions.")


class ResourceGrantScope(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    permissions = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    permission_vocabulary = ()

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        validate_permission_set(self.permissions, self.permission_vocabulary)


class ResourceStaffGrant(ResourceGrantScope):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(app_label)s_staff_grants",
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+",
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        abstract = True


class ResourceStaffGrantInvite(ResourceGrantScope):
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    email_digest = models.CharField(max_length=64, blank=True, default="", editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+",
    )
    expires_at = models.DateTimeField(default=invite_expiry)
    redeemed_at = models.DateTimeField(null=True, blank=True)
    redeemed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta:
        abstract = True
