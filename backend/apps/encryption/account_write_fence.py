"""Global→tenant→account lock order and persistent account epoch checks."""

from contextlib import contextmanager
from contextvars import ContextVar

from django.db import connection, transaction

from apps.encryption.account_models import AccountPiiKey, PiiAccountWriteFence
from apps.encryption.crypto import PiiUnavailable
from apps.encryption.models import PiiGlobalWriteFence, PiiMakerspaceWriteFence
from apps.encryption.write_fence import (
    GLOBAL_LOCK_NAMESPACE, TENANT_LOCK_NAMESPACE, PiiWriteFenced,
)

ACCOUNT_LOCK_NAMESPACE = 734_203
_held = ContextVar("account_pii_fences", default=None)


class AccountKeyChanged(PiiUnavailable):
    code = "account_key_changed"
    status_code = 409


def _lock(namespace, key, *, exclusive=False):
    function = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {function}(%s, %s)", [namespace, key])


def _assert_open(row, operation):
    allowed = {"enable_transition", "decrypt_rollback", "search_rotation", "tenant_import"}
    if row is None or (row.state != "open" and not (
        row.operation_id is not None and str(row.operation_id) == operation
        and row.operation_kind in allowed
    )):
        raise PiiWriteFenced("Protected writes are temporarily unavailable.")


@contextmanager
def account_fences(account_ids, tenant_ids=(), *, exclusive=False, allow_erased=False):
    """Caller owns the source boundary and atomic block before invoking this helper."""
    if not connection.in_atomic_block:
        raise RuntimeError("Account fences require an atomic transaction.")
    accounts, tenants = frozenset(map(int, account_ids)), frozenset(map(int, tenant_ids))
    if any(value <= 0 or value > 2147483647 for value in accounts | tenants):
        raise ValueError("Invalid fence scope.")
    held = _held.get()
    if held is not None:
        if not accounts <= held[0] or not tenants <= held[1] or (exclusive and not held[2]):
            raise RuntimeError("Cannot expand mapped-write scopes after acquiring fences.")
        if not allow_erased and PiiAccountWriteFence.objects.filter(user_id__in=accounts, state="erased").exists():
            raise AccountKeyChanged("Account key changed.")
        yield
        return
    _lock(GLOBAL_LOCK_NAMESPACE, 0)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.pii_fence_operation', true)")
        operation = cursor.fetchone()[0]
    _assert_open(PiiGlobalWriteFence.objects.filter(pk=1).first(), operation)
    for tenant_id in sorted(tenants):
        _lock(TENANT_LOCK_NAMESPACE, tenant_id)
        _assert_open(PiiMakerspaceWriteFence.objects.filter(makerspace_id=tenant_id).first(),
                     operation)
    for user_id in sorted(accounts):
        _lock(ACCOUNT_LOCK_NAMESPACE, user_id, exclusive=exclusive)
        state = PiiAccountWriteFence.objects.filter(user_id=user_id).values_list("state", flat=True).first()
        if state == PiiAccountWriteFence.State.ERASED:
            if allow_erased:
                # Retained tenant history may be read/updated under the lock.
                # Account-key/vault writers use default fences and epoch checks.
                continue
            raise AccountKeyChanged("Account key changed.")
        if state is not None and state != PiiAccountWriteFence.State.OPEN:
            raise PiiWriteFenced("Protected writes are temporarily unavailable.")
    token = _held.set((accounts, tenants, exclusive))
    try:
        yield
    finally:
        _held.reset(token)


def assert_account_fence_held(user_id, *, exclusive=False):
    held = _held.get()
    if held is None or int(user_id) not in held[0] or (exclusive and not held[2]):
        raise RuntimeError("Declare the account fence before acquiring domain locks.")


def verify_prepared_epoch(user_id, epoch, version=None):
    """Nonlocking reads are protected by the declared shared advisory account lock."""
    assert_account_fence_held(user_id)
    fence = PiiAccountWriteFence.objects.filter(user_id=user_id).first()
    if fence is None or fence.state != fence.State.OPEN or fence.epoch != epoch:
        raise AccountKeyChanged("Account key changed.")
    if version is not None and not AccountPiiKey.objects.filter(
        user_id=user_id, version=version, status=AccountPiiKey.Status.ACTIVE,
    ).exists():
        raise AccountKeyChanged("Account key changed.")


validate_key_epoch = verify_prepared_epoch


@contextmanager
def account_write(user_id, *, exclusive=False):
    """Account-only boundary is independent of unrelated tenant migration state."""
    from apps.tenant_migration.gate_locks import shared_boundary

    held = _held.get()
    if held is not None:
        with account_fences([user_id], exclusive=exclusive):
            yield PiiAccountWriteFence.objects.get(user_id=user_id)
        return
    if connection.in_atomic_block:
        raise RuntimeError("Account writes must acquire the source boundary before atomic().")
    with shared_boundary(0), transaction.atomic(), account_fences([user_id], exclusive=exclusive):
        yield PiiAccountWriteFence.objects.filter(user_id=user_id).first()
