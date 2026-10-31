"""Unusual-login check state: remembered devices, familiar networks and alert links (S0 schema).

Deployment-local authentication telemetry, never tenant data. Raw identifiers never land
here: a device and a network are stored as keyed HMACs, an alert link as a SHA-256 digest
of its nonce; the readable labels are short-lived and cleared on the retention schedule in
``login_security_contract.RETENTION``. S-B owns every behaviour.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from .login_security_contract import ALERT_KINDS, NETWORK_GRANULARITIES


class KnownDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="known_devices")
    device_hmac = models.CharField(max_length=64)
    ua_label = models.CharField(max_length=120, blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)
    last_verified_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "device_hmac"), name="known_device_unique_per_user"),
        ]

    def __str__(self):
        return f"device:{self.pk}"


class KnownNetwork(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="known_networks")
    granularity = models.CharField(max_length=16, choices=[(value, value) for value in NETWORK_GRANULARITIES])
    prefix_hmac = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    last_seen = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("user", "granularity", "prefix_hmac"),
                                    name="known_network_unique_per_user"),
            models.CheckConstraint(condition=models.Q(granularity__in=NETWORK_GRANULARITIES),
                                   name="known_network_granularity_known"),
        ]
        indexes = [models.Index(fields=("last_seen",), name="known_network_last_seen")]

    def __str__(self):
        return f"network:{self.pk}"


class SecurityAlert(models.Model):
    """One alert email and its single-use "this wasn't me" link."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_alerts")
    kind = models.CharField(max_length=24, choices=[(value, value) for value in ALERT_KINDS])
    nonce_digest = models.CharField(max_length=64, unique=True)
    network_label = models.CharField(max_length=120, null=True, blank=True)
    ua_label = models.CharField(max_length=120, null=True, blank=True)
    sent_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(kind__in=ALERT_KINDS), name="security_alert_kind_known"),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("sent_at")),
                                   name="security_alert_expires_after_sending"),
        ]
        indexes = [models.Index(fields=("expires_at",), name="security_alert_expiry")]

    def __str__(self):
        return f"alert:{self.kind}:{self.pk}"
