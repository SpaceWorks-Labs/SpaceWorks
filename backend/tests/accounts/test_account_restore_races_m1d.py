"""Separate Postgres connections prove the purge fence survives every commit gap."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event

import pytest
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts import account_purge
from apps.accounts.account_restore import identifier_fingerprint, restore_locked
from apps.accounts.account_restore_email import confirm_email
from apps.accounts.models import User, PasswordResetEnvelope
from apps.accounts.models_account_purge import AccountPurgeObject, AccountPurgeProgress
from tests.accounts import deletion_factories as f
from tests.accounts.restore_helpers_m1d import PASSWORD, archive, email_proof, expire, restore_config
from tests.accounts.test_account_deletion_races import connected
from tests.accounts.test_support_m1d import m1d_config, purge

pytestmark = pytest.mark.django_db(transaction=True)


def restore_outcome(user_id, fingerprint):
    try:
        with transaction.atomic():
            user = User.objects.select_for_update(no_key=True).get(pk=user_id)
            restore_locked(user, fingerprint=fingerprint, new_password=PASSWORD)
        return "restored"
    except ValidationError:
        return "refused"


@pytest.mark.parametrize("pause_at", ["before_first_tenant", "between_tenants", "during_object_cleanup"])
def test_purge_fence_is_committed_before_scrub_and_prevents_restore_in_every_gap(pause_at, monkeypatch):
    user, one, two = archive(), f.space(), f.space()
    f.request(user, one)
    f.request(user, two)
    token = email_proof(user)
    expire(user)
    paused, checked = Event(), Event()
    original_scrub, original_finish = account_purge._scrub, account_purge._finish_tenant

    def pause():
        paused.set()
        assert checked.wait(timeout=8)

    def scrub(pk, tenant):
        if pause_at == "before_first_tenant" and tenant == one.pk:
            pause()
        original_scrub(pk, tenant)
        if pause_at == "during_object_cleanup" and tenant == one.pk:
            # A real durable byte journal remains pending while the object store is busy.
            AccountPurgeObject.objects.create(user_id=pk, makerspace_id=tenant, bucket="public",
                object_key="restore-race-image", size_bytes=0)

    def finish(pk, tenant):
        original_finish(pk, tenant)
        if pause_at == "between_tenants" and tenant == one.pk:
            assert AccountPurgeProgress.objects.get(user_id=pk, makerspace_id=tenant).done_at
            pause()

    from apps.accounts import account_purge_objects as objects
    original_drain = objects.drain
    def drain(subject, tenant):
        if pause_at == "during_object_cleanup" and tenant == one.pk:
            pause()
            AccountPurgeObject.objects.filter(user=subject, makerspace_id=tenant).update(
                deleted_at=timezone.now(), quota_released_at=timezone.now())
        else:
            original_drain(subject, tenant)

    monkeypatch.setattr(account_purge, "_scrub", scrub)
    monkeypatch.setattr(account_purge, "_finish_tenant", finish)
    monkeypatch.setattr(objects, "drain", drain)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(connected, lambda: purge(user))
        try:
            assert paused.wait(timeout=8)
            # This connection cannot see an uncommitted fence from the worker.
            locked = User.objects.get(pk=user.pk)
            assert locked.purge_started_at
            assert not connection.in_atomic_block
            # Even an operator extending the deadline after the first scrub cannot
            # reopen recovery. This isolates the fence from the ordinary date check.
            User.objects.filter(pk=user.pk).update(deletion_purge_after=timezone.now() + timedelta(days=1))
            with pytest.raises(ValidationError):
                confirm_email(user.email, token, PASSWORD)
            locked.refresh_from_db()
            assert not locked.is_active and locked.deletion_requested_at
        finally:
            checked.set()
        assert future.result(timeout=15)["purged"] == 1


def test_restore_holds_user_lock_until_commit_and_stale_purge_call_then_skips(monkeypatch):
    user = archive()
    fingerprint = identifier_fingerprint(user)
    started = Event()
    original = account_purge.alias_tenant_ids  # purge discovery reads alias_tenant_ids now (see git log)
    def never_scrub(subject):
        if not subject.deletion_requested_at:
            raise AssertionError("restored account reached purge discovery")
        return original(subject)
    monkeypatch.setattr(account_purge, "alias_tenant_ids", never_scrub)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
            restore_locked(locked, fingerprint=fingerprint, new_password=PASSWORD)
            def stale_purge():
                started.set()
                return purge(user)
            future = pool.submit(connected, stale_purge)
            assert started.wait(timeout=5)
        assert future.result(timeout=15)["purged"] == 0
    user.refresh_from_db()
    assert user.is_active and user.purge_started_at is None


def test_restore_waiting_for_purge_user_lock_refuses_the_committed_fence():
    user = archive()
    fingerprint = identifier_fingerprint(user)
    started = Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            locked = User.objects.select_for_update(no_key=True).get(pk=user.pk)
            locked.purge_started_at = timezone.now()
            locked.save(update_fields=["purge_started_at"])
            def restore():
                started.set()
                return restore_outcome(user.pk, fingerprint)
            future = pool.submit(connected, restore)
            assert started.wait(timeout=5)
        assert future.result(timeout=15) == "refused"
    user.refresh_from_db()
    assert not user.is_active


def test_final_purge_and_email_confirmation_use_user_before_envelope_lock_order(monkeypatch):
    from apps.accounts import recovery_locks
    user = archive()
    address, token = user.email, email_proof(user)
    expire(user)
    waiting = Event()
    original = recovery_locks.usable
    def candidate(row, purpose, now):
        result = original(row, purpose, now)
        if result:
            # Signal immediately before the recovery helper waits on the User lock.
            waiting.set()
        return result
    monkeypatch.setattr(recovery_locks, "usable", candidate)
    def confirm():
        try:
            confirm_email(address, token, PASSWORD)
            return "restored"
        except ValidationError:
            return "refused"
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic():
            User.objects.select_for_update(no_key=True).get(pk=user.pk)
            future = pool.submit(connected, confirm)
            assert waiting.wait(timeout=5)
            # The old envelope-before-User order fails this NOWAIT assertion.
            PasswordResetEnvelope.objects.select_for_update(nowait=True).get(user=user)
            counts = {"purged": 0, "skipped": 0, "failed": 0}
            account_purge._finish_global(user.pk, set(), counts)
            assert counts["purged"] == 1
        assert future.result(timeout=15) == "refused"
