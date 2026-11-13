"""Credentials that act as a person (#196): personal access tokens and OAuth app connections.

A personal access token is shown once and stored only as a SHA-256 digest of 256 bits
of randomness (no hand-rolled crypto: the digest is a lookup key for an unguessable
value, compared in constant time). OAuth tokens, codes and client secrets are
django-oauth-toolkit's own models; this module adds who registered an app for which
space, and each person's consent, which carries the MFA proof captured at consent.
"""
from django.utils.translation import gettext_lazy
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

PAT_PREFIX = "swpat_"
DEFAULT_TTL_DAYS, MAX_TTL_DAYS = 90, 365


def digest(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


class PersonalAccessToken(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="personal_access_tokens")
    makerspace = models.ForeignKey("makerspaces.Makerspace", null=True, blank=True, on_delete=models.CASCADE,
                                   related_name="personal_access_tokens",
                                   help_text=gettext_lazy("The one space staff scopes apply to."))
    name = models.CharField(max_length=120)
    lookup = models.CharField(max_length=16, unique=True, editable=False)
    token_digest = models.CharField(max_length=64, editable=False)
    scopes = models.JSONField(default=list)
    # The MFA proof of the session that created it; a factor reset invalidates the token.
    mfa_claims = models.JSONField(default=dict, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @classmethod
    def issue(cls, *, user, name, scopes, makerspace, days, mfa_claims):
        lookup = secrets.token_hex(8)
        raw = f"{PAT_PREFIX}{lookup}_{secrets.token_urlsafe(32)}"
        row = cls.objects.create(user=user, name=name, scopes=list(scopes), makerspace=makerspace,
                                 lookup=lookup, token_digest=digest(raw), mfa_claims=dict(mfa_claims),
                                 expires_at=timezone.now() + timedelta(days=days))
        return row, raw

    @property
    def active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()


class OAuthAppRegistration(models.Model):
    """Which space an OAuth application belongs to, and the scopes it may ask for."""
    application = models.OneToOneField(settings.OAUTH2_PROVIDER_APPLICATION_MODEL, on_delete=models.CASCADE,
                                       related_name="spaceworks_registration")
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="oauth_apps")
    allowed_scopes = models.JSONField(default=list)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="registered_oauth_apps")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class OAuthConsent(models.Model):
    """A person's live consent to one app: the Connected apps list, and the MFA proof."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="oauth_consents")
    application = models.ForeignKey(settings.OAUTH2_PROVIDER_APPLICATION_MODEL, on_delete=models.CASCADE,
                                    related_name="spaceworks_consents")
    scopes = models.JSONField(default=list)
    mfa_claims = models.JSONField(default=dict, editable=False)
    granted_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "application"], name="oauth_consent_one_per_app")]
