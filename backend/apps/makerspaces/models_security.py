"""Platform locks on per-space security settings (owner decisions #110c, #111 Q9).

A lock is a floor set by a platform superadmin: the space may tighten the setting but
never loosen it below ``floor``, and only a superadmin removes the lock. Rows are written
only by ``apps.makerspaces.security_settings``; every write is audited there.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class MakerspaceSecurityLock(models.Model):
    makerspace = models.ForeignKey(
        "makerspaces.Makerspace", on_delete=models.CASCADE, related_name="security_locks",
    )
    key = models.CharField(max_length=100)
    floor = models.JSONField()
    note = models.CharField(max_length=200, blank=True, default="")
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+",
    )
    locked_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("makerspace", "key"), name="makerspace_security_lock_unique_key"),
        ]
        ordering = ("key",)

    def __str__(self):
        return f"{self.makerspace_id}:{self.key}"
