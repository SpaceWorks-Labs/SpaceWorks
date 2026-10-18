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
    if connection.in_atomic_block:
        raise RuntimeError("Prepare project keys before domain transactions.")
    from apps.events.models_event import Event
    from apps.encryption.services import unwrap_dek
    tenant_id = Event.objects.values_list("makerspace_id", flat=True).get(pk=event_id)
    keys = list(MakerspaceEncryptionKey.objects.filter(makerspace_id=tenant_id).exclude(status="disabled"))
    active = [key for key in keys if key.status == "active"]
    if len(active) != 1:
        raise SubmissionError("pii_unavailable", 503)
    try:
        prepared = (tenant_id, active[0].version, {key.version: unwrap_dek(key) for key in keys})
    except PiiUnavailable as exc:
        raise SubmissionError("pii_unavailable", 503) from exc
    token = _prepared.set(prepared)
    try:
        yield
    finally:
        _prepared.reset(token)


def _keys(tenant_id):
    prepared = _prepared.get()
    if prepared is None or prepared[0] != tenant_id:
        raise SubmissionError("pii_preparation_required", 503)
    if not MakerspaceEncryptionKey.objects.filter(makerspace_id=tenant_id,
            version=prepared[1], status="active").exists():
        raise SubmissionError("pii_key_changed", 409)
    return prepared[1], prepared[2]


class PrivateDocumentMixin(ScopedPiiModelMixin):
    pii_document_fields = frozenset()
    pii_text_fields = frozenset()

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
                _, keys = _keys(tenant_id)
                plain = decrypt_with_key_loader(raw, makerspace_id=tenant_id, table=self._meta.db_table,
                    pk=self.pk, field=name, load_dek=lambda v: keys[v]).decode("utf-8")
                self.__dict__.setdefault("_pii_plain_values", {})[name] = plain
        value = super().__getattribute__(name)
        if (name in type(self).pii_document_fields and isinstance(value, str)
                and not self.__dict__.get("_document_saving")):
            return json.loads(value)
        return value

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
            version, keys = _keys(tenant_id)
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
