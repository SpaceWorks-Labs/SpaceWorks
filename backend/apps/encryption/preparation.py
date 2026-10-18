"""Prepare tenant key custody before domain locks; never refill a locked cache."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps

from django.conf import settings
from django.db import connection, transaction

from .crypto import PiiKeyUnavailable
from .models import MakerspaceEncryptionKey

_prepared = ContextVar("prepared_tenant_pii_keys", default=None)
_domain_locked = ContextVar("prepared_tenant_domain_locked", default=False)


def _identity(row):
    return (row.pk, row.version, row.status, row.wrapped_dek, row.broker_backend, row.broker_key_id)


@contextmanager
def prepare_tenants(tenant_ids):
    tenants = tuple(sorted(set(tenant_ids)))
    if not settings.PII_ENCRYPTION_ENABLED:
        yield
        return
    held = _prepared.get()
    if held is not None:
        if not set(tenants) <= held.keys():
            raise PiiKeyUnavailable()
        yield
        return
    if connection.in_atomic_block:
        raise RuntimeError("Prepare tenant keys before domain transactions.")
    from .services import get_or_create_active_dek, unwrap_dek
    prepared = {}
    for tenant_id in tenants:
        get_or_create_active_dek(tenant_id)
        rows = list(MakerspaceEncryptionKey.objects.filter(makerspace_id=tenant_id).exclude(status="disabled"))
        active = [row for row in rows if row.status == "active"]
        if len(active) != 1:
            raise PiiKeyUnavailable()
        prepared[tenant_id] = (active[0], {row.version: unwrap_dek(row) for row in rows},
                               tuple(_identity(row) for row in rows))
    token = _prepared.set(prepared)
    try:
        yield
    finally:
        _prepared.reset(token)


def prepared_keys(tenant_id):
    held = _prepared.get()
    if held is None or tenant_id not in held:
        raise PiiKeyUnavailable()
    active, keys, identities = held[tenant_id]
    live = MakerspaceEncryptionKey.objects.filter(makerspace_id=tenant_id).exclude(status="disabled")
    if {_identity(row) for row in live} != set(identities):
        raise PiiKeyUnavailable()
    return active, keys


def active_preparation():
    return _prepared.get() is not None


def tenant_key_change(function):
    """Serialize key rotation/disable/rewrap against shared programme tenant fences."""
    @wraps(function)
    def wrapped(makerspace_id, *args, **kwargs):
        from .write_fence import GLOBAL_LOCK_NAMESPACE, TENANT_LOCK_NAMESPACE
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock_shared(%s, %s)", [GLOBAL_LOCK_NAMESPACE, 0])
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [TENANT_LOCK_NAMESPACE, makerspace_id])
            return function(makerspace_id, *args, **kwargs)
    return wrapped


def require_prepared_for_programme(tenant_id):
    """Cache hits never bypass a prepared epoch; no locked cache refill exists."""
    if active_preparation():
        return prepared_keys(tenant_id)
    if connection.in_atomic_block and _domain_locked.get():
        raise PiiKeyUnavailable()
    return None


@contextmanager
def locked_domain():
    token = _domain_locked.set(True)
    try:
        yield
    finally:
        _domain_locked.reset(token)
