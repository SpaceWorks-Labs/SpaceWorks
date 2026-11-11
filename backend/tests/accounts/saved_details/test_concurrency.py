from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from django.db import close_old_connections, transaction

from apps.accounts.saved_details import intents
from apps.accounts.saved_details.lifecycle import erase_account_vault
from apps.accounts.saved_details.models import MemberSavedDetail, SavedDetailUpdateIntent
from apps.encryption.account_services import prepare_account_key, revoke_account_keys
from apps.encryption.account_write_fence import AccountKeyChanged, account_fences
from apps.tenant_migration.gate_locks import shared_boundary

from .test_intents import insert, prepared

pytestmark = pytest.mark.django_db(transaction=True)


def connected(run):
    close_old_connections()
    try:
        return run()
    finally:
        close_old_connections()


def test_two_intents_with_same_base_apply_once_and_preserve_newer_value(owner, monkeypatch):
    first = prepared(owner)
    second = prepared(owner, values={"institution": "Second college"})
    ids = [insert(owner, *bundle, monkeypatch) for bundle in (first, second)]
    barrier = threading.Barrier(2)

    def apply(pk):
        def run():
            barrier.wait(timeout=10)
            intents.apply_intent(pk)
        return connected(run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apply, pk) for pk in ids]
        for future in futures:
            future.result(timeout=20)
    assert sorted(SavedDetailUpdateIntent.objects.values_list("state", flat=True)) == ["applied", "conflict"]
    assert MemberSavedDetail.objects.get(user=owner, field_key="institution").version == 1


def test_shared_event_account_fence_blocks_exclusive_key_revocation(owner):
    prepare_account_key(owner.pk)
    entered, finished = threading.Event(), threading.Event()

    def revoke():
        def run():
            entered.set()
            revoke_account_keys(owner.pk, owner)
            finished.set()
        return connected(run)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with shared_boundary(0), transaction.atomic(), account_fences([owner.pk]):
            future = pool.submit(revoke)
            assert entered.wait(10)
            assert not finished.wait(0.2)
        future.result(timeout=10)
        assert finished.is_set()


def test_erase_between_prepare_and_insert_prevents_resurrection(owner, monkeypatch):
    bundle = prepared(owner)
    erase_account_vault(owner.pk, actor=owner)
    with pytest.raises(AccountKeyChanged):
        insert(owner, *bundle, monkeypatch)
    assert not SavedDetailUpdateIntent.objects.filter(user=owner).exists()
    assert not MemberSavedDetail.objects.filter(user=owner).exists()
