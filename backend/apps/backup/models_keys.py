"""Platform key rotation state (release 2 L11, BK-68).

One row per age recipient fingerprint this deployment has used, per kind: the platform
key (``BACKUP_AGE_RECIPIENT``) or this server's restore key
(``TENANT_MIGRATION_AGE_RECIPIENT``). A rotation retires the previous fingerprints, and
a retired fingerprint is refused for every later archive build, so an old (possibly
compromised) key is never used again. Fingerprints are SHA-256 of the canonical public
recipient: public facts, never key material.
"""
from django.utils.translation import gettext_lazy
from django.conf import settings
from django.db import models
from django.utils import timezone


class BackupKeyFingerprint(models.Model):
    class Kind(models.TextChoices):
        PLATFORM = "platform", gettext_lazy("Platform key")
        SERVER = "server", gettext_lazy("This server's restore key")

    kind = models.CharField(max_length=16, choices=Kind.choices)
    fingerprint = models.CharField(max_length=64)
    first_seen_at = models.DateTimeField(default=timezone.now)
    retired_at = models.DateTimeField(null=True, blank=True)
    retired_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ("kind", "-first_seen_at")
        constraints = [models.UniqueConstraint(fields=("kind", "fingerprint"), name="backup_key_fingerprint_once")]

    def __str__(self):
        state = "retired" if self.retired_at else "current"
        return f"{self.get_kind_display()} {self.fingerprint[:12]}… ({state})"
