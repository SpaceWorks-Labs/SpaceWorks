"""Where a space's image-adapter provider lives: per makerspace, or one for the whole platform (decision 314(c)).

Same shape as the wallet credentials: the shared secret is encrypted at rest through `apps.makerspaces.secrets`
and is WRITE-ONLY (what a person may read back is "configured" and a short public fingerprint). A space row wins
over the platform row; the platform row is a singleton the superadmin owns. Neither travels in a data export or
a tenant move (a moved space enters its own again).
"""
import hashlib

from django.db import models

from apps.makerspaces.secrets import decrypt_value, encrypt_value


class ImageAdapterFields(models.Model):
    provider_url = models.CharField(max_length=300, blank=True, default="")
    secret = models.TextField(blank=True, default="")
    secret_fingerprint = models.CharField(max_length=12, blank=True, default="")
    last_test_at = models.DateTimeField(null=True, blank=True)
    last_test_ok = models.BooleanField(null=True, blank=True)
    last_test_error = models.CharField(max_length=40, blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def get_secret(self):
        return decrypt_value(self.secret) if self.secret else ""

    def set_secret(self, raw):
        self.secret = encrypt_value(raw) if raw else ""
        self.secret_fingerprint = hashlib.sha256(raw.encode()).hexdigest()[:12] if raw else ""

    @property
    def complete(self):
        return bool(self.provider_url and self.secret)

    def clear(self):
        self.provider_url, self.secret, self.secret_fingerprint = "", "", ""
        self.last_test_at, self.last_test_ok, self.last_test_error = None, None, ""


class MakerspaceImageAdapter(ImageAdapterFields):
    makerspace = models.OneToOneField("makerspaces.Makerspace", on_delete=models.CASCADE,
                                      related_name="image_adapter")
    # May the platform's provider serve this space when it has none of its own? No row = ON; this records an opt-out.
    use_platform_provider = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "makerspace image adapters"


class PlatformImageAdapter(ImageAdapterFields):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        verbose_name_plural = "platform image adapter"

    @classmethod
    def load(cls):
        return cls.objects.filter(pk=1).first() or cls()
