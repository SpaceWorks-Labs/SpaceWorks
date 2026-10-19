"""Prepare mandatory finance keys before entering domain transactions."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from django.db import connection, transaction
from django.db.models import Max

from .crypto import PiiKeyUnavailable
from .models import MakerspaceEncryptionKey

_contexts = ContextVar("prepared_tenant_keys", default={})


@dataclass(frozen=True)
class TenantKeyContext:
    makerspace_id: int
    version: int
    dek: bytes = field(repr=False)
    retained_deks: tuple = field(default=(), repr=False)


@contextmanager
def tenant_key_context(context):
    token = _contexts.set({**_contexts.get(), context.makerspace_id: context})
    try:
        yield context
    finally:
        _contexts.reset(token)


def prepared_tenant_key(makerspace_id):
    context = _contexts.get().get(makerspace_id)
    if context is None:
        raise PiiKeyUnavailable()
    # No broker/key row locks within the domain transaction. The shared tenant
    # fence prevents disable_dek from racing this metadata validation and INSERT.
    if not MakerspaceEncryptionKey.objects.filter(
        makerspace_id=makerspace_id, version=context.version, status="active",
    ).exists():
        raise PiiKeyUnavailable()
    return context


def holds_tenant_key(makerspace_id):
    return makerspace_id in _contexts.get()


def prepared_tenant_read_key(makerspace_id, version):
    context = _contexts.get().get(makerspace_id)
    if context is None:
        return None
    if context.version == version:
        return context.dek
    return dict(context.retained_deks).get(version)


def prepare_tenant_key(makerspace_id, *, create=True):
    """Reuse the broker/AAD protocol; publish a wrapped candidate after I/O."""
    if connection.in_atomic_block:
        raise PiiKeyUnavailable()  # prepare the tenant key before starting the command
    from .services import configured_broker, unwrap_dek, _audit
    from .write_fence import assert_mapped_write_allowed
    from apps.makerspaces.models import Makerspace

    keys = MakerspaceEncryptionKey.objects.filter(makerspace_id=makerspace_id)
    def context_for(key, dek):
        retained = tuple((row.version, unwrap_dek(row)) for row in keys.exclude(
            status="disabled",
        ).exclude(version=key.version))
        return TenantKeyContext(makerspace_id, key.version, dek, retained)
    for _ in range(3):
        active = keys.filter(status="active").first()
        if active is not None:
            return context_for(active, unwrap_dek(active))
        if not create:
            raise PiiKeyUnavailable()
        latest = keys.aggregate(version=Max("version"))["version"] or 0
        broker = configured_broker()
        wrapped = broker.create_dek(makerspace_id, latest + 1)
        with transaction.atomic():
            assert_mapped_write_allowed(makerspace_id)
            space = Makerspace.objects.select_for_update().get(pk=makerspace_id)
            if keys.filter(status="active").exists():
                continue
            if (keys.aggregate(version=Max("version"))["version"] or 0) != latest:
                continue
            key = keys.create(
                makerspace=space, version=latest + 1, wrapped_dek=wrapped.wrapped_dek,
                broker_backend=broker.backend, broker_key_id=wrapped.broker_key_id,
            )
            _audit("encryption.dek_created", space, [key.version])
        return context_for(key, wrapped.dek)
    raise PiiKeyUnavailable()


@contextmanager
def mandatory_write_context(instance, fields):
    mandatory = [item for item in fields if item.encryption_required]
    if not mandatory:
        yield
        return
    from .registry import makerspace_id_for
    tenant_id = makerspace_id_for(instance, mandatory[0])
    context = _contexts.get().get(tenant_id)
    if context is None:
        context = prepare_tenant_key(tenant_id)
    with tenant_key_context(context):
        yield
