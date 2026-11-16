"""Wallet-pass signing credentials, per makerspace or for the whole platform (decision 223(l)).

Apple: a Pass Type ID, the Team ID, the signing certificate + private key and Apple's WWDR
intermediate. Google: the issuer id, a class prefix and the service-account JSON.

Every secret is encrypted at rest through `apps.makerspaces.secrets` and is WRITE-ONLY: no
serializer, export, report or audit row ever carries one. What a person may read back is the
public fingerprint and the Apple certificate's expiry. A space row wins over the platform row
(`wallet/credentials.py` resolves them); the platform row is a singleton the superadmin owns.
These models never travel in a data export or a tenant move (a moved space re-enters its own).
"""
from django.db import models

from apps.makerspaces.secrets import decrypt_value, encrypt_value

SECRET_FIELDS = ("apple_cert_pem", "apple_key_pem", "apple_wwdr_pem", "google_service_account")


class WalletCredentialFields(models.Model):
    apple_pass_type_id = models.CharField(max_length=120, blank=True, default="")
    apple_team_id = models.CharField(max_length=20, blank=True, default="")
    apple_cert_pem = models.TextField(blank=True, default="")
    apple_key_pem = models.TextField(blank=True, default="")
    apple_wwdr_pem = models.TextField(blank=True, default="")
    apple_cert_fingerprint = models.CharField(max_length=64, blank=True, default="")
    apple_cert_expires_at = models.DateTimeField(null=True, blank=True)
    google_issuer_id = models.CharField(max_length=32, blank=True, default="")
    google_class_prefix = models.CharField(max_length=40, blank=True, default="spaceworks_card")
    google_service_account = models.TextField(blank=True, default="")
    google_key_fingerprint = models.CharField(max_length=64, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def secret(self, name):
        return decrypt_value(getattr(self, name)) if getattr(self, name) else ""

    def set_secret(self, name, raw):
        setattr(self, name, encrypt_value(raw) if raw else "")

    @property
    def apple_complete(self):
        return bool(self.apple_pass_type_id and self.apple_team_id and self.apple_cert_pem and self.apple_key_pem
                    and self.apple_wwdr_pem)

    @property
    def google_complete(self):
        return bool(self.google_issuer_id and self.google_service_account)

    def clear_apple(self):
        self.apple_pass_type_id = self.apple_team_id = self.apple_cert_fingerprint = ""
        self.apple_cert_pem = self.apple_key_pem = self.apple_wwdr_pem = ""
        self.apple_cert_expires_at = None

    def clear_google(self):
        self.google_issuer_id = self.google_service_account = self.google_key_fingerprint = ""
        self.google_class_prefix = "spaceworks_card"


class MakerspaceWalletCredentials(WalletCredentialFields):
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="wallet_credentials")
    # Decision 281: may the platform's certificates sign this space's passes when it has none of its own?
    # A space with no row at all is also ON (the default), so this only ever records an opt-out.
    use_platform_credentials = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "makerspace wallet credentials"


class PlatformWalletCredentials(WalletCredentialFields):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        verbose_name_plural = "platform wallet credentials"

    @classmethod
    def load(cls):
        return cls.objects.filter(pk=1).first() or cls()
