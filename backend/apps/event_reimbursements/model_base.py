"""Common row shape; concrete workflow modules remain the only state writers."""

from django.db import models


class Versioned(models.Model):
    version = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Immutable(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            from apps.payments.event_payouts.model_base import maintenance_fields
            allowed = maintenance_fields(self)
            requested = kwargs.get("update_fields")
            if requested is not None and not set(requested) <= allowed:
                raise RuntimeError("Maintenance may update mapped envelopes only.")
            kwargs["update_fields"] = allowed if requested is None else requested
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Financial history requires an authorized purge.")
