"""Dictionary-facing documents over the existing text-envelope PII mapper.

The mapper authenticates a single serialized document. Domain code still reads
and assigns dictionaries; raw exports must use the mapped field, never values().
"""
import json
from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings
from django.db import connection, transaction

from apps.encryption.mappers import ScopedPiiModelMixin
from apps.encryption.crypto import decrypt_with_key_loader, encrypt, is_envelope, PiiUnavailable
from apps.encryption.models import MakerspaceEncryptionKey
from apps.encryption.registry import makerspace_id_for, field_for
from .errors import SubmissionError

_prepared = ContextVar("event_project_document_keys", default=None)


@contextmanager
def prepare_documents(event_id):
    """All broker work precedes the source/fence/event transaction."""
    if not settings.PII_ENCRYPTION_ENABLED:
        yield
        return
    from apps.events.models_event import Event
    from apps.encryption.preparation import prepare_tenants, prepared_keys
    tenant_id = Event.objects.values_list("makerspace_id", flat=True).get(pk=event_id)
    with prepare_tenants([tenant_id]):
        active, keys = prepared_keys(tenant_id)
        token = _prepared.set((tenant_id, active.version, keys))
        try:
            yield
        finally:
            _prepared.reset(token)



class _OnDemandKeys(dict):
    """Version -> DEK, unwrapped through the shared encryption services when asked."""

    def __init__(self, tenant_id):
        super().__init__()
        self.tenant_id = tenant_id

    def __missing__(self, version):
        from apps.encryption.services import get_dek
        return get_dek(self.tenant_id, version)


def _keys(tenant_id, *, on_demand=False, write=True):
    prepared = _prepared.get()
    if prepared is None or prepared[0] != tenant_id:
        from apps.encryption.preparation import (
            active_preparation, prepared_keys, require_prepared_for_programme)
        if active_preparation():
            active, keys = prepared_keys(tenant_id)
            return active.version, keys
        if not on_demand:
            raise SubmissionError("pii_preparation_required", 503)
        # Legacy registration writers predate preparation. Outside a locked event
        # domain they keep the shared mapper's on-demand key custody (it refuses
        # under one); values are still encrypted, never stored as plaintext.
        require_prepared_for_programme(tenant_id)
        keys = _OnDemandKeys(tenant_id)
        if not write:
            return None, keys
        from apps.encryption.services import get_or_create_active_dek
        active = get_or_create_active_dek(tenant_id)
        keys[active.key.version] = active.dek
        return active.key.version, keys
    if not MakerspaceEncryptionKey.objects.filter(makerspace_id=tenant_id,
            version=prepared[1], status="active").exists():
        raise SubmissionError("pii_key_changed", 409)
    return prepared[1], prepared[2]


class PrivateDocumentMixin(ScopedPiiModelMixin):
    pii_document_fields = frozenset()
    pii_text_fields = frozenset()
    # Programme rows refuse to save without preparation; a legacy model whose
    # existing writers predate it may opt into on-demand custody outside locks.
    pii_on_demand_keys = False

    class Meta:
        abstract = True

    def __setattr__(self, name, value):
        if name in type(self).pii_document_fields and isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
        super().__setattr__(name, value)

    def __getattribute__(self, name):
        if name in (type(self).pii_document_fields | type(self).pii_text_fields) and settings.PII_ENCRYPTION_ENABLED:
            raw = self.__dict__.get(name)
            if is_envelope(raw) and connection.in_atomic_block:
                tenant_id = makerspace_id_for(self, field_for(self, name))
                _, keys = _keys(tenant_id, on_demand=type(self).pii_on_demand_keys, write=False)
                plain = decrypt_with_key_loader(raw, makerspace_id=tenant_id, table=self._meta.db_table,
                    pk=self.pk, field=name, load_dek=lambda v: keys[v]).decode("utf-8")
                self.__dict__.setdefault("_pii_plain_values", {})[name] = plain
        value = super().__getattribute__(name)
        if (name in type(self).pii_document_fields and isinstance(value, str)
                and not self.__dict__.get("_document_saving")):
            return json.loads(value)
        return value

    def clean_fields(self, exclude=None):
        # TextField.clean would stringify a dict using Python repr and destroy JSON.
        # The document boundary serializes strictly on assignment; validators own schema.
        return super().clean_fields(exclude=set(exclude or ()) | type(self).pii_document_fields)

    def save(self, *args, **kwargs):
        selected = kwargs.get("update_fields")
        names = self._private_names(selected)
        if settings.PII_ENCRYPTION_ENABLED and names:
            from apps.encryption.write_fence import assert_mapped_write_allowed
            tenant_id = makerspace_id_for(self, field_for(self, next(iter(names))))
            with transaction.atomic():
                assert_mapped_write_allowed(tenant_id)
                return self._save_documents(*args, **kwargs)
        return self._save_documents(*args, **kwargs)

    def _save_documents(self, *args, **kwargs):
        selected = kwargs.get("update_fields")
        names = self._private_names(selected)
        names = {name for name in names if self.__dict__.get(name) not in (None, "")}
        if settings.PII_ENCRYPTION_ENABLED and names:
            tenant_id = makerspace_id_for(self, field_for(self, next(iter(names))))
            version, keys = _keys(tenant_id, on_demand=type(self).pii_on_demand_keys)
            if self.pk is None:
                self._reserve_pk()
            for name in names:
                raw = self.__dict__[name]
                if raw in (None, ""):
                    continue
                if is_envelope(raw):
                    plain = decrypt_with_key_loader(raw, makerspace_id=tenant_id, table=self._meta.db_table,
                        pk=self.pk, field=name, load_dek=lambda v: keys[v]).decode("utf-8")
                else:
                    plain = raw
                envelope = encrypt(plain.encode(), keys[version], key_version=version,
                    makerspace_id=tenant_id, table=self._meta.db_table, pk=self.pk, field=name)
                self.__dict__[name] = envelope
                # The shared mapper reuses these prepared envelopes; it never
                # provisions or unwraps a key from inside this transaction.
                for cache, value in (("_pii_raw_values", envelope), ("_pii_plain_values", plain),
                                     ("_pii_original_plain_values", plain)):
                    self.__dict__.setdefault(cache, {})[name] = value
        self.__dict__["_document_saving"] = True
        try:
            return super().save(*args, **kwargs)
        finally:
            self.__dict__.pop("_document_saving", None)

    def _private_names(self, selected):
        names = (type(self).pii_document_fields | type(self).pii_text_fields) - self.get_deferred_fields()
        return names if selected is None else names.intersection(selected)
