from django.conf import settings
from django.db import models


class PlatformLimitDefault(models.Model):
    """Decision 328a: the platform-wide default for ONE limit key (every space that sets none of its own).

    Resolution order: the space's own override, then a hosted space's plan, then this default, then no limit.
    No row means unlimited (the default for every key). Only the superadmin writes it (audited); deployment
    level, never part of a tenant dump. Every write clears the cached map.
    """

    key = models.CharField(max_length=64, unique=True)
    value = models.PositiveBigIntegerField(help_text="Whole units of the key (bytes for byte keys). Delete the row for no limit.")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)

    def __str__(self):
        return f"{self.key}={self.value}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from .limit_defaults import invalidate
        invalidate()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        from .limit_defaults import invalidate
        invalidate()
        return result


class SpaceLimitThreshold(models.Model):
    """Decision 328a: the last warning level (80 or 100 percent) a space was told about for one key.

    One row per (space, key) that has crossed a threshold; it exists only so the sweep notifies once per
    crossing and resets when usage drops back under 80 percent (the row is deleted then). Derived,
    re-creatable state: it never travels in a tenant dump (a target deployment re-derives it).
    """

    makerspace = models.ForeignKey("makerspaces.Makerspace", on_delete=models.CASCADE, related_name="limit_thresholds")
    key = models.CharField(max_length=64)
    level = models.PositiveSmallIntegerField(help_text="80 or 100: the highest threshold already notified.")
    notified_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("makerspace", "key"), name="space_limit_threshold_once")]

    def __str__(self):
        return f"{self.makerspace_id}:{self.key}@{self.level}"
