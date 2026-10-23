"""Two-phase account DEK preparation: no broker calls while rows are locked."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import timedelta
from uuid import uuid4

from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.services import record
from apps.encryption.account_models import AccountPiiKey, PiiAccountWriteFence
from apps.encryption.account_readiness import (
    assert_ready, get_broker, require_outside_transaction,
)
from apps.encryption.account_write_fence import (
    AccountKeyChanged, account_write, assert_account_fence_held, verify_prepared_epoch,
)
from apps.encryption.crypto import PiiUnavailable

_contexts = ContextVar("account_pii_prepared_keys", default={})


class AccountKeyUnavailable(PiiUnavailable):
    code = "account_key_unavailable"
    status_code = 503


class AccountKeyPreparing(PiiUnavailable):
    code = "account_key_preparing"
    status_code = 409
    retry_after = 2


@dataclass(frozen=True)
class AccountKeyContext:
    user_id: int
    version: int
    epoch: int
    dek: bytes = field(repr=False)


@contextmanager
def account_key_context(context):
    """Supply already-unwrapped material to an explicit mapper write boundary."""
    contexts = dict(_contexts.get())
    contexts[(context.user_id, context.version)] = context
    token = _contexts.set(contexts)
    try:
        yield context
    finally:
        _contexts.reset(token)


def prepared_key(user_id, version):
    context = _contexts.get().get((int(user_id), version))
    if context is None:
        raise AccountKeyUnavailable("Prepare the account key before starting the command.")
    return context


def _owner(user_id, *, locked=False):
    query = User.objects.select_for_update() if locked else User.objects
    user = query.get(pk=user_id)
    if (not user.is_active or user.account_kind != User.AccountKind.MEMBER
            or user.is_tenant_dump_stub or user.is_walk_in or user.retired_at is not None
            or user.access_status != User.AccessStatus.ACTIVE):
        raise AccountKeyUnavailable("Account key unavailable.")
    return user


def _unwrap(key, epoch):
    try:
        dek = get_broker(key.broker_backend).unwrap_dek(
            key.wrapped_dek, key.user_id, key.version, broker_key_id=key.broker_key_id,
        )
        return AccountKeyContext(key.user_id, key.version, epoch, dek)
    except Exception as exc:
        raise AccountKeyUnavailable("Account key unavailable.") from exc


def get_account_key(user_id, version=None):
    """Read a specific retained version; disabled or missing keys never fall back."""
    require_outside_transaction()
    assert_ready()
    _owner(user_id)
    fence = PiiAccountWriteFence.objects.filter(user_id=user_id, state="open").first()
    keys = AccountPiiKey.objects.filter(user_id=user_id).exclude(status="disabled")
    key = keys.filter(version=version).first() if version is not None else keys.filter(status="active").first()
    if fence is None or key is None:
        raise AccountKeyUnavailable("Account key unavailable.")
    context = _unwrap(key, fence.epoch)
    # Recheck after the broker round trip; an erasure/rotation cannot issue a usable
    # stale context. The event insertion still rechecks under its own shared fence.
    with account_write(user_id):
        verify_prepared_epoch(user_id, context.epoch)
    return context


def prepare_account_key(user_id):
    require_outside_transaction()
    assert_ready()
    claim_id, now = uuid4(), timezone.now()
    with account_write(user_id, exclusive=True):
        user = _owner(user_id, locked=True)
        fence, _ = PiiAccountWriteFence.objects.select_for_update().get_or_create(user_id=user_id)
        active = AccountPiiKey.objects.select_for_update().filter(user_id=user_id, status="active").first()
        if active is None:
            if (fence.claim_id is not None and fence.claim_expires_at is not None
                    and fence.claim_expires_at > now):
                raise AccountKeyPreparing("Account key preparing.")
            version = (AccountPiiKey.objects.filter(user_id=user_id).aggregate(v=Max("version"))["v"] or 0) + 1
            fence.claim_id, fence.claim_expires_at = claim_id, now + timedelta(seconds=60)
            fence.save(update_fields=["claim_id", "claim_expires_at", "updated_at"])
            record(user, "account_pii.key_preparation_claimed", target=fence,
                   meta={"version": version})
        epoch = fence.epoch
    if active is not None:
        return get_account_key(user_id, active.version)
    try:
        broker = get_broker()
        wrapped = broker.create_dek(user_id, version)
    except Exception as exc:
        with account_write(user_id, exclusive=True):
            user = _owner(user_id, locked=True)
            fence = PiiAccountWriteFence.objects.select_for_update().get(user_id=user_id)
            if fence.claim_id == claim_id:
                fence.claim_id, fence.claim_expires_at = None, None
                fence.save(update_fields=["claim_id", "claim_expires_at", "updated_at"])
                record(user, "account_pii.key_preparation_failed", target=fence)
        raise AccountKeyUnavailable("Account key unavailable.") from exc
    with account_write(user_id, exclusive=True):
        user = _owner(user_id, locked=True)
        fence = PiiAccountWriteFence.objects.select_for_update().get(user_id=user_id)
        if (fence.claim_id != claim_id or fence.epoch != epoch
                or fence.claim_expires_at <= timezone.now()):
            raise AccountKeyChanged("Account key changed.")
        key = AccountPiiKey.objects.create(user=user, version=version,
            wrapped_dek=wrapped.wrapped_dek, broker_backend=broker.backend,
            broker_key_id=wrapped.broker_key_id)
        fence.claim_id, fence.claim_expires_at = None, None
        fence.save(update_fields=["claim_id", "claim_expires_at", "updated_at"])
        record(user, "account_pii.key_created", target=key, meta={"version": version})
    return AccountKeyContext(user_id, version, epoch, wrapped.dek)


def revoke_account_keys(user_id, actor, *, erase=False):
    """Caller erases vault/intent rows first in the same exclusive account command."""
    with account_write(user_id, exclusive=True):
        assert_account_fence_held(user_id, exclusive=True)
        user = User.objects.select_for_update().get(pk=user_id)
        fence = PiiAccountWriteFence.objects.select_for_update().get(user_id=user_id)
        fence.epoch += 1
        fence.claim_id, fence.claim_expires_at = None, None
        fence.save(update_fields=["epoch", "claim_id", "claim_expires_at", "updated_at"])
        keys = AccountPiiKey.objects.select_for_update().filter(user_id=user_id)
        if erase:
            from django.apps import apps
            from apps.encryption.account_registry import registered_labels

            for label in registered_labels():
                if apps.get_model(label).objects.filter(user_id=user_id).exists():
                    raise RuntimeError("Erase account PII rows before destroying keys.")
            keys.delete()
            fence.state = fence.State.ERASED
            fence.save(update_fields=["state", "updated_at"])
        else:
            keys.update(status=AccountPiiKey.Status.DISABLED)
        record(actor, "account_pii.keys_erased" if erase else "account_pii.keys_revoked",
               target=user, meta={"epoch": fence.epoch})


def rotate_account_key(user_id, actor):
    """Retain old decryptable versions; invalidate pre-rotation prepared intents.

    Pending intents with the previous epoch must be explicitly retried/migrated by
    the account worker. This function never silently authorizes an old epoch.
    """
    require_outside_transaction()
    assert_ready()
    claim_id, now = uuid4(), timezone.now()
    with account_write(user_id, exclusive=True):
        _owner(user_id, locked=True)
        fence = PiiAccountWriteFence.objects.select_for_update().get(user_id=user_id)
        if fence.claim_id is not None and fence.claim_expires_at and fence.claim_expires_at > now:
            raise AccountKeyPreparing("Account key preparing.")
        active = AccountPiiKey.objects.select_for_update().get(user_id=user_id, status="active")
        version = AccountPiiKey.objects.filter(user_id=user_id).aggregate(v=Max("version"))["v"] + 1
        epoch = fence.epoch
        fence.claim_id, fence.claim_expires_at = claim_id, now + timedelta(seconds=60)
        fence.save(update_fields=["claim_id", "claim_expires_at", "updated_at"])
        record(actor, "account_pii.rotation_claimed", target=fence, meta={"version": version})
    try:
        broker = get_broker()
        wrapped = broker.create_dek(user_id, version)
    except Exception as exc:
        # The bounded claim expires; the prior live key remains untouched.
        raise AccountKeyUnavailable("Account key unavailable.") from exc
    with account_write(user_id, exclusive=True):
        _owner(user_id, locked=True)
        fence = PiiAccountWriteFence.objects.select_for_update().get(user_id=user_id)
        if (fence.claim_id != claim_id or fence.epoch != epoch
                or fence.claim_expires_at <= timezone.now()):
            raise AccountKeyChanged("Account key changed.")
        old = AccountPiiKey.objects.select_for_update().get(pk=active.pk)
        if old.status != old.Status.ACTIVE:
            raise AccountKeyChanged("Account key changed.")
        old.status = old.Status.ROTATED
        old.save(update_fields=["status"])
        key = AccountPiiKey.objects.create(user_id=user_id, version=version,
            wrapped_dek=wrapped.wrapped_dek, broker_backend=broker.backend,
            broker_key_id=wrapped.broker_key_id)
        fence.epoch += 1
        fence.claim_id, fence.claim_expires_at = None, None
        fence.save(update_fields=["epoch", "claim_id", "claim_expires_at", "updated_at"])
        record(actor, "account_pii.key_rotated", target=key, meta={"version": version, "epoch": fence.epoch})
        return AccountKeyContext(user_id, version, fence.epoch, wrapped.dek)
