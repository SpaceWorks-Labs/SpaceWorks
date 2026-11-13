"""Conservative free admission. Provider I/O never runs under the ledger lock."""
import hashlib
import uuid
from contextvars import ContextVar
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.storage_capabilities.contracts import CapabilityError
from .database import accounting_transaction

_pending = ContextVar("cloud_server_reservations", default=None)


def pending_key(identity, key):
    value = (_pending.get() or {}).get((identity, key))
    return value[0] if value and value[1] == _owner_tag() else None


def _owner_tag():
    from apps.backup.managed.capture import _capture
    capture = _capture.get()
    if capture is not None:
        return "capture:" + str(capture[0])
    from apps.operations.cloud_runtime import _writer
    writer = _writer.get()
    return (str(writer.row.pk), writer.row.generation) if writer else None


def clear_pending(identity, key):
    values = dict(_pending.get() or {})
    values.pop((identity, key), None)
    _pending.set(values)


def enabled():
    return getattr(settings, "SPACEWORKS_DEPLOYMENT_PROFILE", "full") == "free"


def identity_for(client, bucket):
    from apps.storage_capabilities.runtime import client_identity
    return client_identity(client, bucket).fingerprint


def object_digest(identity, key):
    return hashlib.sha256(f"{identity}\0{key}".encode()).hexdigest()


def reserve_upload(client, *, bucket, key, max_bytes, ttl, makerspace_id=None, server_owned=False):
    if not enabled():
        return None
    if type(max_bytes) is not int or max_bytes < 1 or type(ttl) is not int or ttl < 1:
        raise CapabilityError("storage_reservation_invalid")
    from apps.operations.models import CloudObjectAccount, CloudObjectReservation
    identity = identity_for(client, bucket)
    pending = pending_key(identity, key) if server_owned else None
    digest = pending or (uuid.uuid4().hex + uuid.uuid4().hex if server_owned else object_digest(identity, key))
    now = timezone.now()
    with accounting_transaction():
        # One deployment lock serializes admission across every configured bucket.
        CloudObjectAccount.objects.get_or_create(identity="deployment")
        CloudObjectAccount.objects.select_for_update().get(pk="deployment")
        account, _ = CloudObjectAccount.objects.get_or_create(identity=identity)
        existing = CloudObjectReservation.objects.filter(pk=digest).first()
        if existing:
            # Replaying an already issued URL cannot acquire a second allowance,
            # but a new URL must not extend its original late-write horizon.
            if server_owned and existing.server_owned and existing.state == "reserved" and existing.bytes >= max_bytes:
                return digest
            if server_owned and existing.state == "finalized":
                clear_pending(identity, key)
                digest = uuid.uuid4().hex + uuid.uuid4().hex
            else:
                raise CapabilityError("storage_reservation_reconciliation_required")
        from apps.storage_capabilities.runtime import configured_contracts
        identities = {c.identity.fingerprint for c in configured_contracts().values()}
        if identity not in identities:
            raise CapabilityError("storage_account_binding_required")
        accounts = list(CloudObjectAccount.objects.select_for_update().filter(pk__in=identities).order_by("pk"))
        if len(accounts) != len(identities) or any(a.used is None or a.sampled_at is None
                or (now - a.sampled_at).total_seconds() > 1800 or a.reason for a in accounts):
            raise CapabilityError("storage_usage_refresh_required")
        pending = CloudObjectReservation.objects.filter(state__in=["reserved", "writing", "uncertain"]).aggregate(n=Sum("bytes"))["n"] or 0
        cap = getattr(settings, "FREE_OBJECT_CAP_BYTES", None)
        if cap is None or sum(a.used for a in accounts) + pending + max_bytes > cap:
            raise CapabilityError("storage_account_cap_reached")
        CloudObjectReservation.objects.create(key=digest, account=account, bytes=max_bytes,
                                             expires_at=now + timedelta(seconds=ttl), server_owned=server_owned)
    if server_owned:
        values = dict(_pending.get() or {})
        values[(identity, key)] = (digest, _owner_tag())
        _pending.set(values)
    return digest


def finalized_upload(client, *, bucket, key, size, operation_key, keep_pending=False, reservation_id=None):
    if not enabled():
        return
    if type(size) is not int or size < 0:
        raise CapabilityError("storage_usage_size_invalid")
    from apps.operations.models import CloudObjectAccount, CloudObjectUsageReceipt, CloudObjectReservation
    identity = identity_for(client, bucket)
    with accounting_transaction():
        account, _ = CloudObjectAccount.objects.get_or_create(identity=identity)
        account = CloudObjectAccount.objects.select_for_update().get(pk=account.pk)
        reservation = CloudObjectReservation.objects.filter(pk=reservation_id or pending_key(identity, key), server_owned=True).first()
        if reservation and reservation.state == "finalized":
            clear_pending(identity, key)
            return  # Shared transport already settled this explicit promotion.
        receipt, created = CloudObjectUsageReceipt.objects.get_or_create(
            operation_key=hashlib.sha256(operation_key.encode()).hexdigest(), defaults={
                "bucket_alias": identity, "object_key_digest": object_digest(identity, key),
                "generation": "", "bytes": size, "operation": "finalize"})
        if (receipt.bucket_alias, receipt.object_key_digest, receipt.bytes, receipt.operation) != (
                identity, object_digest(identity, key), size, "finalize"):
            raise CapabilityError("storage_receipt_identity_mismatch")
        if created and account.used is not None:
            account.used += size
            account.save(update_fields=["used"])
        CloudObjectReservation.objects.filter(pk=reservation.pk if reservation else None, server_owned=True,
                                              state__in=["reserved", "writing"]).update(state="finalized")
        # Keep presign reservations charged: staging URLs remain writable after
        # finalization, and retained versions can consume more physical bytes.
    if not keep_pending:
        clear_pending(identity, key)


def confirmed_delete(client, *, bucket, key, result, operation_key, started_at=None):
    if not enabled():
        return
    if not result.absence_confirmed or result.key != key:
        raise CapabilityError("storage_delete_unconfirmed")
    from apps.operations.models import CloudObjectAccount, CloudObjectUsageReceipt
    identity = identity_for(client, bucket)
    with accounting_transaction():
        account, _ = CloudObjectAccount.objects.get_or_create(identity=identity)
        account = CloudObjectAccount.objects.select_for_update().get(pk=account.pk)
        # Unknown observed bytes invalidate the sample; they never mean zero.
        if result.bytes_observed is None:
            account.reason = "storage_deleted_bytes_unknown"
            account.save(update_fields=["reason"])
            return
        receipt, created = CloudObjectUsageReceipt.objects.get_or_create(
            operation_key=hashlib.sha256(operation_key.encode()).hexdigest(), defaults={
                "bucket_alias": identity, "object_key_digest": object_digest(identity, key),
                "generation": "", "bytes": result.bytes_observed, "operation": "delete_confirmed"})
        if (receipt.bucket_alias, receipt.object_key_digest, receipt.operation) != (
                identity, object_digest(identity, key), "delete_confirmed"):
            raise CapabilityError("storage_receipt_identity_mismatch")
        # A non-atomic listing may already exclude a deletion that started during
        # its pages. Never subtract that same physical disappearance again.
        safe_credit = (started_at is not None and account.sampled_at is not None
                       and account.sampled_at < started_at and account.started_at is None)
        if created and account.used is not None and safe_credit:
            account.used = max(0, account.used - result.bytes_observed)
            account.save(update_fields=["used"])
