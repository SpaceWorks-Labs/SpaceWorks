"""Explicit browser-upload renewal keeps one deployment debt and its binding."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import transaction
from django.utils import timezone

from apps.operations.cloud_quotas import storage
from apps.operations.models import CloudObjectAccount, CloudObjectReservation
from apps.storage_capabilities.contracts import CapabilityError

pytestmark = [pytest.mark.django_db, pytest.mark.area_platform]
IDENTITY = "c" * 64
ARGS = {"bucket": "private", "key": "staging/evidence", "max_bytes": 4, "ttl": 300}


@pytest.fixture
def admission(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "free"
    settings.FREE_OBJECT_CAP_BYTES = 10
    clock = SimpleNamespace(now=timezone.now())
    monkeypatch.setattr(timezone, "now", lambda: clock.now)
    monkeypatch.setattr(storage, "identity_for", lambda *args: IDENTITY)
    monkeypatch.setattr("apps.storage_capabilities.runtime.configured_contracts", lambda: {
        "private": SimpleNamespace(identity=SimpleNamespace(fingerprint=IDENTITY))})
    account = CloudObjectAccount.objects.create(identity=IDENTITY, used=6, sampled_at=clock.now, reason="")
    return account, clock


def rows():
    return list(CloudObjectReservation.objects.order_by("pk").values())


def test_explicit_renewal_retains_exact_debt_at_cap_and_covers_slow_signing(admission):
    account, clock = admission
    original = storage.reserve_upload(None, **ARGS)
    expiry = CloudObjectReservation.objects.get(pk=original).expires_at
    clock.now = expiry - timedelta(seconds=1)
    with transaction.atomic():
        renewed = storage.reserve_upload(None, **ARGS, renew=True)
        assert renewed == original
        clock.now += timedelta(seconds=7)  # Signing can cross the old horizon.
        storage.cover_upload_authorization(renewed, ttl=300)
    row = CloudObjectReservation.objects.get()
    assert (row.pk, row.account_id, row.bytes, row.state, row.server_owned, row.expires_at) == (
        original, account.pk, 4, "reserved", False, clock.now + timedelta(seconds=300))
    account.refresh_from_db()
    assert account.used == 6


def test_an_ordinary_presign_cannot_reuse_or_extend_the_original_debt(admission):
    storage.reserve_upload(None, **ARGS)
    before = rows()
    with pytest.raises(CapabilityError) as failure:
        storage.reserve_upload(None, **ARGS)
    assert failure.value.code == "storage_reservation_reconciliation_required"
    assert rows() == before


@pytest.mark.parametrize("closed", [
    "expiry", "writing", "uncertain", "reconciled", "inventoried", "finalized", "released",
    "server_owned", "bytes", "missing", "account",
])
def test_closed_expired_or_mismatched_client_reservation_cannot_renew(admission, closed):
    _, clock = admission
    key = storage.reserve_upload(None, **ARGS)
    if closed == "expiry":
        clock.now = CloudObjectReservation.objects.get(pk=key).expires_at
    elif closed == "missing":
        CloudObjectReservation.objects.filter(pk=key).delete()
    elif closed == "account":
        other = CloudObjectAccount.objects.create(identity="d" * 64)
        CloudObjectReservation.objects.filter(pk=key).update(account=other)
    elif closed in {"server_owned", "bytes"}:
        CloudObjectReservation.objects.filter(pk=key).update(**{closed: True if closed == "server_owned" else 5})
    else:
        CloudObjectReservation.objects.filter(pk=key).update(state=closed)
    before = rows()
    with pytest.raises(CapabilityError) as failure, transaction.atomic():
        storage.reserve_upload(None, **ARGS, renew=True)
    assert failure.value.code == "storage_reservation_reconciliation_required"
    assert rows() == before


@pytest.mark.parametrize("changed,code", [
    ("cap", "storage_account_cap_reached"),
    ("stale", "storage_usage_refresh_required"),
    ("unknown", "storage_usage_refresh_required"),
    ("binding", "storage_account_binding_required"),
])
def test_renewal_rechecks_deployment_capacity_and_configured_account(admission, changed, code, settings, monkeypatch):
    account, clock = admission
    storage.reserve_upload(None, **ARGS)
    if changed == "cap":
        settings.FREE_OBJECT_CAP_BYTES = 9
    elif changed == "stale":
        account.sampled_at = clock.now - timedelta(seconds=1801)
        account.save(update_fields=["sampled_at"])
    elif changed == "unknown":
        account.used = None
        account.save(update_fields=["used"])
    else:
        monkeypatch.setattr("apps.storage_capabilities.runtime.configured_contracts", lambda: {})
    before = rows()
    with pytest.raises(CapabilityError) as failure, transaction.atomic():
        storage.reserve_upload(None, **ARGS, renew=True)
    assert failure.value.code == code
    assert rows() == before


def test_failed_signing_or_coverage_rolls_back_the_renewal_horizon(admission):
    _, clock = admission
    key = storage.reserve_upload(None, **ARGS)
    before = rows()
    clock.now += timedelta(seconds=10)
    with pytest.raises(RuntimeError, match="signer failed"), transaction.atomic():
        renewed = storage.reserve_upload(None, **ARGS, renew=True)
        storage.cover_upload_authorization(renewed, ttl=300)
        raise RuntimeError("signer failed")
    assert rows() == before
    with pytest.raises(CapabilityError) as failure, transaction.atomic():
        storage.reserve_upload(None, **ARGS, renew=True)
        CloudObjectReservation.objects.filter(pk=key).update(state="reconciled")
        storage.cover_upload_authorization(key, ttl=300)
    assert failure.value.code == "storage_reservation_reconciliation_required"
    assert rows() == before


def test_full_profile_renewal_never_queries_cloud_accounts(settings, monkeypatch):
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    def forbidden(*args):
        raise AssertionError("Full profile accessed free accounting")
    monkeypatch.setattr(storage, "identity_for", forbidden)
    assert storage.reserve_upload(None, **ARGS, renew=True) is None
