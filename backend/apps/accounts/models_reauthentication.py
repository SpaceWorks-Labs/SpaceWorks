"""Server-owned browser step-up proof; never exported as tenant authority."""

from django.conf import settings
from django.db import models


class ReauthenticationSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=128, unique=True)
    surface = models.CharField(max_length=16)
    auth_generation = models.CharField(max_length=64)
    credential_fingerprint = models.CharField(max_length=64)
    mfa_version = models.CharField(max_length=36, blank=True)
    auth_time = models.DateTimeField(null=True)
    social_verified_at = models.DateTimeField(null=True)
    enrollment_confirmed_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
