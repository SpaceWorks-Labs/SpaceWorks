"""Platform IP access: superadmin allow/deny rules and automatic blocks (S0 schema).

Global, never per space (#128 C-2: a space's own staff allow-list is a security-policy
setting). Rules are platform configuration and automatic blocks are short-lived
telemetry; neither exports or travels. S-C owns every behaviour.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from .login_security_contract import IP_ACTIONS


class IPAccessRule(models.Model):
    # Canonical network text (``ipaddress.ip_network(..., strict=False)``), e.g. 203.0.113.0/24.
    cidr = models.CharField(max_length=49, unique=True)
    action = models.CharField(max_length=8, choices=[(value, value) for value in IP_ACTIONS])
    note = models.CharField(max_length=200, blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(action__in=IP_ACTIONS), name="ip_access_rule_action_known"),
            models.CheckConstraint(condition=~models.Q(cidr=""), name="ip_access_rule_cidr_present"),
        ]

    def __str__(self):
        return f"{self.action}:{self.cidr}"


class IPAutoBlock(models.Model):
    # Keyed HMAC of the blocked source (address or network); the lookup key.
    ip_key = models.CharField(max_length=64, unique=True)
    # The raw network, for the superadmin's list only; deleted with the row after expiry.
    network = models.CharField(max_length=49)
    blocked_until = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=("blocked_until",), name="ip_auto_block_until")]

    def __str__(self):
        return f"auto_block:{self.pk}"
