"""Deployment credentials for server-side native app verification."""

from django.db import models

from apps.makerspaces.secrets import decrypt_value, encrypt_value


class PlatformAttestationSettings(models.Model):
    class Meta:
        # #188: plain-language admin name (the default plural was broken English).
        verbose_name = "app attestation settings"
        verbose_name_plural = "app attestation settings"

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    app_display_name = models.CharField(max_length=100, default="SpaceWorks")
    play_integrity_service_account = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def set_play_integrity_service_account(self, raw):
        self.play_integrity_service_account = encrypt_value(raw) if raw else ""

    def get_play_integrity_service_account(self):
        return decrypt_value(self.play_integrity_service_account) if self.play_integrity_service_account else ""

    def __str__(self):
        return "Platform attestation settings"
