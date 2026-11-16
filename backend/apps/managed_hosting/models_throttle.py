from django.conf import settings
from django.db import models


class PlatformThrottleRate(models.Model):
    """One superadmin override of a DRF throttle scope's rate (platform level, never in a tenant dump).

    The env/settings value stays the default; deleting the row restores it. Every write
    clears the cached override map so the next request sees it.
    """

    scope = models.CharField(max_length=64, unique=True)
    rate = models.CharField(max_length=16)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("scope",)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .throttle_rates import invalidate
        invalidate()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from .throttle_rates import invalidate
        invalidate()
        return result
