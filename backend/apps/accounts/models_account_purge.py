"""Durable account erasure work; credentials never travel in tenant exports."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AccountPurgeProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    done_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "makerspace"], name="uniq_account_purge_tenant",
        )]


class AccountPurgeObject(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE)
    bucket = models.CharField(max_length=255)
    object_key = models.CharField(max_length=500)
    size_bytes = models.PositiveBigIntegerField()
    deleted_at = models.DateTimeField(null=True, blank=True)
    quota_released_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=128, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "makerspace", "bucket", "object_key"], name="uniq_account_purge_object",
        )]


class AppleRefreshCredential(models.Model):
    social_identity = models.ForeignKey("accounts.SocialIdentity", on_delete=models.CASCADE)
    client_id = models.CharField(max_length=255)
    token_ciphertext = models.TextField()
    version = models.UUIDField(default=uuid.uuid4)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["social_identity", "client_id"], name="uniq_apple_refresh_client",
        )]


class AppleRevocation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Empty denotes an older Apple identity with no stored credential.
    client_id = models.CharField(max_length=255, blank=True)
    token_ciphertext = models.TextField(blank=True, default="")
    credential_id = models.PositiveBigIntegerField(null=True, blank=True)
    credential_version = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=128, blank=True, default="")
    done_at = models.DateTimeField(null=True, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(
            fields=["user", "client_id", "credential_version"], name="uniq_apple_revocation_version",
        )]
