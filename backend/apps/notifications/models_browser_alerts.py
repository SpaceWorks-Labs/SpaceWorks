"""Browser notifications (W3C Web Push, VAPID) and staff-notice escalation state.

Browser alerts are opt-in per person per space. The push service endpoint and the
subscription's auth secret are capabilities, so both are stored as Fernet ciphertext
and never echoed by the API; `endpoint_sha256` identifies a subscription without them.
Native and watch push are a different system (`notifications/*push*`, L19).
"""

from django.conf import settings
from django.db import models

from apps.makerspaces.secrets import decrypt_value, encrypt_value


class BrowserAlertSubscription(models.Model):
    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    endpoint = models.TextField()
    endpoint_sha256 = models.CharField(max_length=64)
    p256dh = models.CharField(max_length=128)
    auth_secret = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    failures = models.PositiveSmallIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "notifications"
        constraints = [models.UniqueConstraint(fields=["makerspace", "user", "endpoint_sha256"],
                                               name="uniq_browser_alert_subscription")]

    def set_secrets(self, endpoint, auth_secret):
        self.endpoint = encrypt_value(endpoint)
        self.auth_secret = encrypt_value(auth_secret)

    def get_endpoint(self):
        return decrypt_value(self.endpoint)

    def get_auth_secret(self):
        return decrypt_value(self.auth_secret)


class NotificationEscalation(models.Model):
    """One re-ping per unseen staff notice (one fan-out identity)."""

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="+")
    event_key = models.UUIDField()
    feature = models.CharField(max_length=32)
    event = models.CharField(max_length=64)
    escalated_at = models.DateTimeField(auto_now_add=True)
    rooms_posted = models.PositiveSmallIntegerField(default=0)

    class Meta:
        app_label = "notifications"
        constraints = [models.UniqueConstraint(fields=["makerspace", "event_key"],
                                               name="uniq_notification_escalation")]
