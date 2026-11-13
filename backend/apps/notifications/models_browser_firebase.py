"""Separate Firebase registration; W3C subscription endpoint semantics remain untouched."""
from django.conf import settings
import uuid
from django.db import models
from apps.makerspaces.secrets import decrypt_value, encrypt_value


class BrowserFirebaseInstallation(models.Model):
    """Platform owner fence; changed only after proof of installation possession."""
    fid_hmac = models.CharField(max_length=64, unique=True)
    owner_epoch = models.UUIDField(default=uuid.uuid4)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "notifications"


class BrowserFirebaseRegistration(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    project_id = models.CharField(max_length=63)
    fid_ciphertext = models.TextField()
    fid_hmac = models.CharField(max_length=64)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    wake_pending_seq = models.PositiveBigIntegerField(default=0)
    wake_sent_seq = models.PositiveBigIntegerField(default=0)
    wake_retry_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "notifications"
        constraints = [models.UniqueConstraint(fields=["makerspace", "user", "project_id", "fid_hmac"],
                                               name="uniq_browser_firebase_person_space")]

    def set_fid(self, value):
        self.fid_ciphertext = encrypt_value(value)

    def get_fid(self):
        return decrypt_value(self.fid_ciphertext)
