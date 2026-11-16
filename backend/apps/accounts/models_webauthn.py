"""Passkeys (WebAuthn): platform credentials and their short-lived ceremonies (lane S0 schema).

A credential is a second factor for staff and a sign-in method for anyone; it is offered,
never forced (#74). Rows are deployment-local platform credentials, never tenant data:
they do not export, and a merge leaves them on the account that registered them. S-A owns
every behaviour (registration, verification, removal, audit).
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from .login_security_contract import CEREMONY_MFA, CEREMONY_PURPOSES, CEREMONY_REGISTRATION


class WebAuthnCredential(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="webauthn_credentials")
    # base64url (no padding) of the authenticator's credential ID (at most 1023 bytes).
    credential_id = models.CharField(max_length=1366, unique=True)
    public_key = models.BinaryField()  # COSE_Key bytes, as the authenticator sent them.
    sign_count = models.PositiveBigIntegerField(default=0)
    transports = models.JSONField(default=list, blank=True)
    aaguid = models.CharField(max_length=36, blank=True, default="")
    backed_up = models.BooleanField(default=False)
    rp_id = models.CharField(max_length=253)
    name = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(credential_id=""), name="webauthn_credential_id_present"),
            models.CheckConstraint(condition=~models.Q(rp_id=""), name="webauthn_credential_rp_id_present"),
        ]
        indexes = [models.Index(fields=("user", "rp_id"), name="webauthn_cred_user_rp")]

    def __str__(self):
        return f"passkey:{self.pk}"


class WebAuthnCeremony(models.Model):
    """One registration or assertion challenge; consumed exactly once before it expires."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=16, choices=[(value, value) for value in CEREMONY_PURPOSES])
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
                             related_name="+")
    challenge = models.CharField(max_length=128, unique=True)  # base64url of >= 32 random bytes
    rp_id = models.CharField(max_length=253)
    origin = models.CharField(max_length=300)
    mfa_challenge = models.ForeignKey("accounts.MFAChallenge", on_delete=models.CASCADE, null=True, blank=True,
                                      related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(purpose__in=CEREMONY_PURPOSES),
                                   name="webauthn_ceremony_purpose_known"),
            # Registering a passkey is always for a signed-in person.
            models.CheckConstraint(condition=~models.Q(purpose=CEREMONY_REGISTRATION) | models.Q(user__isnull=False),
                                   name="webauthn_ceremony_registration_has_user"),
            # A second-factor assertion answers exactly one first-factor challenge.
            models.CheckConstraint(
                condition=~models.Q(purpose=CEREMONY_MFA) | models.Q(mfa_challenge__isnull=False, user__isnull=False),
                name="webauthn_ceremony_mfa_has_challenge"),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("created_at")),
                                   name="webauthn_ceremony_expires_after_creation"),
        ]
        indexes = [models.Index(fields=("expires_at",), name="webauthn_ceremony_expiry")]

    def __str__(self):
        return f"webauthn:{self.purpose}:{self.pk}"
