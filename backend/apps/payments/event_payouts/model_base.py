"""Core-only model primitives; no imports from removable domain packages."""

from django.db import models
from django.core.exceptions import ImproperlyConfigured
from apps.encryption.mappers import ScopedPiiModelMixin, ScopedPiiQuerySet
from apps.encryption.registry import field_for


class RequiredPiiQuerySet(ScopedPiiQuerySet):
    def _guard(self, names):
        if set(names).intersection(self.model.mandatory_pii_fields):
            raise RuntimeError("Mandatory finance PII requires model.save().")
        return super()._guard(names)

    def bulk_create(self, objs, **kwargs):
        raise RuntimeError("Mandatory finance PII requires model.save().")


class RequiredPii(ScopedPiiModelMixin):
    """Fail closed until G installs the shared mandatory-encryption extension.

    There is no finance-specific crypto implementation. The shared mapper still
    handles envelopes, AAD, keys and fences. Unregistered models must never gain a
    plaintext write path while optional deployment PII mode is disabled.
    """

    mandatory_pii_fields = ()
    objects = models.Manager.from_queryset(RequiredPiiQuerySet)()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        for name in self.mandatory_pii_fields:
            mapping = field_for(self, name)
            if mapping is None or not getattr(mapping, "encryption_required", False):
                raise ImproperlyConfigured("Mandatory finance encryption registration is unavailable.")
        return super().save(*args, **kwargs)


class Immutable(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError("Core finance history is append-only.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Core finance history requires whole-tenant purge.")
