"""Core-only model primitives; no imports from removable domain packages."""

from django.db import connection, models
from django.core.exceptions import ImproperlyConfigured
from apps.encryption.mappers import ScopedPiiModelMixin, ScopedPiiQuerySet
from apps.encryption.registry import field_for, fields_for, makerspace_id_for


def maintenance_fields(instance):
    """The mapper marks envelope writes; PostgreSQL still proves the closed fence.

    Limit the actual UPDATE to mapped columns even if maintenance called save()
    without update_fields. The DB history trigger also compares all other columns.
    Ordinary mapper writes do not qualify without the matching closed operation.
    """
    fields = fields_for(instance)
    if not instance.__dict__.get("_pii_writing") or not fields or not connection.in_atomic_block:
        raise RuntimeError("Financial history is immutable.")
    tenant_id = makerspace_id_for(instance, fields[0])
    with connection.cursor() as cursor:
        cursor.execute("SELECT reimbursement_maintenance_allowed(%s)", [tenant_id])
        if cursor.fetchone()[0] is not True:
            raise RuntimeError("Financial history is immutable.")
    return {item.field_name for item in fields}


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
            allowed = maintenance_fields(self)
            requested = kwargs.get("update_fields")
            if requested is not None and not set(requested) <= allowed:
                raise RuntimeError("Maintenance may update mapped envelopes only.")
            kwargs["update_fields"] = allowed if requested is None else requested
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Core finance history requires whole-tenant purge.")
