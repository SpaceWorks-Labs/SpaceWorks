"""Envelope-only save boundary; no implicit key I/O or plaintext model attributes."""

from contextlib import contextmanager
from contextvars import ContextVar

from django.db import models

from apps.encryption.account_crypto import decrypt, parse_envelope
from apps.encryption.account_registry import fields_for
from apps.encryption.account_services import account_key_context, prepared_key  # re-export
from apps.encryption.account_write_fence import (
    assert_account_fence_held, verify_prepared_epoch,
)
from apps.encryption.crypto import PiiUnavailable, UnmappedPiiModel

_prepared_write = ContextVar("account_pii_prepared_envelope_write", default=None)


@contextmanager
def prepared_envelope_write(user_id, version, epoch):
    """Internal event adapter, after validating the opaque preparation capability.

    No key material or account row lock is needed at insertion. This narrowly
    permits only a new intent row; ordinary vault writes still authenticate GCM.
    """
    assert_account_fence_held(user_id)
    verify_prepared_epoch(user_id, epoch, version)
    token = _prepared_write.set((int(user_id), version, epoch))
    try:
        yield
    finally:
        _prepared_write.reset(token)


class AccountPiiQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if set(kwargs).intersection(getattr(self.model, "account_identity_fields", ())) or any(item.field_name in kwargs or item.owner_field in kwargs
               or item.owner_field.removesuffix("_id") in kwargs for item in fields_for(self.model)):
            raise RuntimeError("Account PII fields require authenticated model.save().")
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, **kwargs):
        if set(fields).intersection(getattr(self.model, "account_identity_fields", ())) or any(item.field_name in fields or item.owner_field in fields
               or item.owner_field.removesuffix("_id") in fields for item in fields_for(self.model)):
            raise RuntimeError("Account PII fields require authenticated model.save().")
        return super().bulk_update(objs, fields, **kwargs)

    def bulk_create(self, objs, **kwargs):
        raise RuntimeError("Account PII models require authenticated model.save().")


class AccountPiiManager(models.Manager.from_queryset(AccountPiiQuerySet)):
    pass


class AccountPiiModelMixin(models.Model):
    """Services explicitly encrypt/decrypt; raw DB/model values remain ciphertext."""

    objects = AccountPiiManager()

    class Meta:
        abstract = True
        base_manager_name = "objects"

    def save(self, *args, **kwargs):
        registered = fields_for(self)
        if not registered:
            raise UnmappedPiiModel("Missing account PII declaration.")
        if self.pk is None:
            raise PiiUnavailable("Allocate the account row UUID before encrypting.")
        identity_fields = getattr(self, "account_identity_fields", ())
        if identity_fields and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(*identity_fields).first()
            if previous is None or any(previous[name] != getattr(self, name) for name in identity_fields):
                raise PiiUnavailable("Protected account row bindings are immutable.")
        update_fields = kwargs.get("update_fields")
        # Even a status-only mutation must remain inside its declared account
        # fence, so erasure cannot race a worker writing an old instance.
        for item in registered:
            assert_account_fence_held(getattr(self, item.owner_field))
        for item in registered:
            if update_fields is not None and item.field_name not in update_fields:
                continue
            user_id = getattr(self, item.owner_field)
            assert_account_fence_held(user_id)
            envelope = self.__dict__.get(item.field_name)
            # Empty ciphertext is only legal for an explicitly erased payload;
            # tombstones and cleaned intents contain no retained private value.
            if envelope == "" and (getattr(self, "deleted_at", None) is not None
                    or getattr(self, "state", None) in {"applied", "conflict", "failed"}):
                continue
            version, _, _ = parse_envelope(envelope)
            prepared = _prepared_write.get()
            if (prepared is not None and self._state.adding
                    and self._meta.label == "accounts.SavedDetailUpdateIntent"
                    and prepared[:2] == (user_id, version)):
                verify_prepared_epoch(user_id, prepared[2], version)
                continue
            context = prepared_key(user_id, version)
            verify_prepared_epoch(user_id, context.epoch)
            plaintext = decrypt(envelope, context.dek, user_id=user_id,
                                table=self._meta.db_table, pk=self.pk, field=item.field_name)
            if len(plaintext) > item.max_bytes:
                raise PiiUnavailable("Account protected value exceeds its size limit.")
        return super().save(*args, **kwargs)
