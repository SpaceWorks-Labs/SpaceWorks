"""Local-only I3 capacity and durable-inventory regression cases."""
from datetime import timedelta
from types import SimpleNamespace
import time

import pytest
from django.utils import timezone

from apps.operations.cloud_quotas import storage
from apps.operations.models import CloudObjectAccount, CloudObjectReservation
from apps.storage_capabilities.contracts import CapabilityError
from apps.storage_capabilities.deletion import DeletionEvidence

IDENTITY = "a" * 64


@pytest.fixture
def account(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    settings.FREE_OBJECT_CAP_BYTES = 1000
    monkeypatch.setattr(storage, "identity_for", lambda *args: IDENTITY)
    monkeypatch.setattr("apps.storage_capabilities.runtime.configured_contracts", lambda: {
        "private": SimpleNamespace(identity=SimpleNamespace(fingerprint=IDENTITY))})
    return CloudObjectAccount.objects.create(identity=IDENTITY, used=100, sampled_at=timezone.now(), reason="")


@pytest.mark.django_db
def test_reservation_blocks_aggregate_cap_and_does_not_extend_url(account):
    key = storage.reserve_upload(None, bucket="private", key="one", max_bytes=800, ttl=10)
    expiry = CloudObjectReservation.objects.get(pk=key).expires_at
    with pytest.raises(CapabilityError, match="reconciliation_required"):
        storage.reserve_upload(None, bucket="private", key="one", max_bytes=800, ttl=1000)
    assert CloudObjectReservation.objects.get(pk=key).expires_at == expiry
    with pytest.raises(CapabilityError, match="storage_account_cap_reached"):
        storage.reserve_upload(None, bucket="private", key="two", max_bytes=101, ttl=10)


@pytest.mark.django_db
def test_stale_or_unknown_usage_never_grants_capacity(account):
    account.sampled_at = timezone.now() - timedelta(hours=1)
    account.save()
    with pytest.raises(CapabilityError, match="refresh_required"):
        storage.reserve_upload(None, bucket="private", key="one", max_bytes=1, ttl=10)


@pytest.mark.django_db
def test_server_finalize_is_once_only_but_browser_late_write_stays_reserved(account):
    server = storage.reserve_upload(None, bucket="private", key="server", max_bytes=100, ttl=10, server_owned=True)
    browser = storage.reserve_upload(None, bucket="private", key="browser", max_bytes=100, ttl=10)
    for _ in range(2):
        storage.finalized_upload(None, bucket="private", key="server", size=90, operation_key="server-generation-1")
    storage.finalized_upload(None, bucket="private", key="browser", size=90, operation_key="browser-generation-1")
    account.refresh_from_db()
    assert account.used == 280
    assert CloudObjectReservation.objects.get(pk=server).state == "finalized"
    assert CloudObjectReservation.objects.get(pk=browser).state == "reserved"


@pytest.mark.django_db
def test_confirmed_delete_credits_exactly_once_unknown_invalidates(account):
    proof = DeletionEvidence("one", 2, bytes_observed=40)
    started = timezone.now()
    storage.confirmed_delete(None, bucket="private", key="one", result=proof, operation_key="receipt-one", started_at=started)
    storage.confirmed_delete(None, bucket="private", key="one", result=proof, operation_key="receipt-one", started_at=started)
    account.refresh_from_db()
    assert account.used == 60
    storage.confirmed_delete(None, bucket="private", key="unknown",
        result=DeletionEvidence("unknown", 1, bytes_observed=None), operation_key="unknown")
    account.refresh_from_db()
    assert account.used == 60 and account.reason == "storage_deleted_bytes_unknown"


@pytest.mark.django_db
def test_delete_started_before_latest_sample_cannot_double_credit(account):
    started = account.sampled_at - timedelta(seconds=1)
    storage.confirmed_delete(None, bucket="private", key="one",
        result=DeletionEvidence("one", 1, bytes_observed=50), operation_key="overlapping-sample", started_at=started)
    account.refresh_from_db()
    assert account.used == 100


@pytest.mark.django_db(transaction=True)
def test_concurrent_admission_shares_one_deployment_cap(account):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import close_old_connections
    barrier = Barrier(2)
    def attempt(key):
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            storage.reserve_upload(None, bucket="private", key=key, max_bytes=600, ttl=60)
            return "accepted"
        except CapabilityError as exc:
            return exc.code
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, ["one", "two"]))
    assert sorted(outcomes) == ["accepted", "storage_account_cap_reached"]


def test_full_profile_never_queries_free_accounts(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    def forbidden(*args):
        raise AssertionError("Full profile accessed free accounting")
    monkeypatch.setattr(storage, "identity_for", forbidden)
    assert storage.reserve_upload(None, bucket="private", key="one", max_bytes=10**30, ttl=10) is None
    storage.finalized_upload(None, bucket="private", key="one", size=10**30, operation_key="one")
    storage.confirmed_delete(None, bucket="private", key="one", result=None, operation_key="one")


def test_incomplete_uploads_are_counted_page_by_page():
    from apps.operations.cloud_quotas.sampling import _multipart
    calls = []
    client = SimpleNamespace(
        list_multipart_uploads=lambda **kwargs: calls.append("uploads") or {
            "Uploads": [{"Key": "one", "UploadId": "u"}], "IsTruncated": False},
        list_parts=lambda **kwargs: calls.append("parts") or {"Parts": [{"Size": 123}], "IsTruncated": False})
    contract = SimpleNamespace(identity=SimpleNamespace(bucket="private"), fingerprint="config")
    amount, cursor, complete = _multipart(client, contract, {"phase": "multipart"})
    assert amount == 0 and not complete and calls == ["uploads"]
    amount, _, complete = _multipart(client, contract, cursor)
    assert amount == 123 and complete and calls == ["uploads", "parts"]


@pytest.mark.django_db
def test_sampler_persists_cursor_and_replays_concurrent_positive_delta(settings, monkeypatch):
    from apps.operations.cloud_quotas import sampling
    from apps.operations.cloud_jobs.contracts import ChunkContext
    from apps.operations.models import CloudObjectUsageReceipt
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    contract = SimpleNamespace(identity=SimpleNamespace(fingerprint=IDENTITY, bucket="private"), fingerprint="config")
    monkeypatch.setattr(sampling, "configured_contracts", lambda: {"private": contract})
    monkeypatch.setattr("apps.operations.cloud_quotas.storage_clients.binding_client", lambda *args: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr(sampling, "usage_page", lambda *args, **kwargs: SimpleNamespace(bytes_observed=100, continuation=None))
    monkeypatch.setattr(sampling, "_multipart", lambda *args: (0, {}, True))
    monkeypatch.setattr(sampling, "_database_sample", lambda: None)
    context = lambda checkpoint: ChunkContext(time.monotonic() + 20, lambda: None, checkpoint, "test", 1)
    result = sampling.sample_storage_chunk(context({}))
    assert not result.complete
    row = CloudObjectAccount.objects.get(pk=IDENTITY)
    assert row.used is None and row.cursor["phase"] == "multipart"
    CloudObjectUsageReceipt.objects.create(operation_key="concurrent", bucket_alias=IDENTITY,
        object_key_digest="b" * 64, generation="", bytes=50, operation="finalize")
    result = sampling.sample_storage_chunk(context(result.checkpoint))
    row.refresh_from_db()
    assert result.complete and row.used == 150 and row.sampled_at is not None
