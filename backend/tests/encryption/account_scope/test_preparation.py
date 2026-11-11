import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from django.db import close_old_connections, connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.encryption import account_services as service
from apps.encryption.account_models import AccountPiiKey, PiiAccountWriteFence
from apps.encryption.account_readiness import get_broker
from apps.encryption.account_write_fence import AccountKeyChanged, account_write, verify_prepared_epoch

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def owner(settings, monkeypatch):
    settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
    settings.ACCOUNT_PII_KEY_BROKER = "local"
    settings.ACCOUNT_PII_MASTER_KEY = Fernet.generate_key().decode()
    settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
    settings.PII_ENCRYPTION_ENABLED = False
    return User.objects.create_user(username=f"saved-{uuid4().hex}")


def test_first_use_claim_wrap_finalize_reuses_one_key_and_never_wraps_in_atomic(owner, monkeypatch):
    broker = get_broker()
    create = broker.create_dek

    def wrap(user_id, version):
        assert not connection.in_atomic_block
        return create(user_id, version)

    monkeypatch.setattr(broker, "create_dek", wrap)
    monkeypatch.setattr(service, "get_broker", lambda *_: broker)
    first = service.prepare_account_key(owner.pk)
    second = service.prepare_account_key(owner.pk)
    assert first == second
    assert AccountPiiKey.objects.filter(user=owner, status="active").count() == 1
    assert PiiAccountWriteFence.objects.get(user=owner).claim_id is None


def test_parallel_creator_observes_retryable_claim_and_winner_is_reusable(owner, monkeypatch):
    broker = get_broker()
    create, entered, release = broker.create_dek, threading.Event(), threading.Event()

    def wrap(user_id, version):
        assert not connection.in_atomic_block
        entered.set()
        assert release.wait(10)
        return create(user_id, version)

    def prepare():
        close_old_connections()
        try:
            return service.prepare_account_key(owner.pk)
        finally:
            close_old_connections()

    monkeypatch.setattr(broker, "create_dek", wrap)
    monkeypatch.setattr(service, "get_broker", lambda *_: broker)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(prepare)
        assert entered.wait(10)
        try:
            with pytest.raises(service.AccountKeyPreparing):
                service.prepare_account_key(owner.pk)
        finally:
            release.set()
        winner = future.result(timeout=10)
    assert service.prepare_account_key(owner.pk) == winner


def test_broker_failure_clears_claim_and_creates_no_active_key(owner, monkeypatch):
    broker = get_broker()
    monkeypatch.setattr(broker, "create_dek", lambda *_: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(service, "get_broker", lambda *_: broker)
    with pytest.raises(service.AccountKeyUnavailable):
        service.prepare_account_key(owner.pk)
    assert not AccountPiiKey.objects.filter(user=owner).exists()
    assert PiiAccountWriteFence.objects.get(user=owner).claim_id is None


def test_stale_claim_can_resume_after_crash(owner):
    PiiAccountWriteFence.objects.create(user=owner, claim_id=uuid4(),
                                       claim_expires_at=timezone.now() - timedelta(seconds=1))
    assert service.prepare_account_key(owner.pk).version == 1


def test_revoke_invalidates_prepared_epoch_and_old_key(owner):
    context = service.prepare_account_key(owner.pk)
    service.revoke_account_keys(owner.pk, owner)
    with account_write(owner.pk), pytest.raises(AccountKeyChanged):
        verify_prepared_epoch(owner.pk, context.epoch, context.version)
    with pytest.raises(service.AccountKeyUnavailable):
        service.get_account_key(owner.pk, context.version)


def test_prepare_forbidden_in_domain_transaction_before_any_broker_io(owner):
    with transaction.atomic(), pytest.raises(RuntimeError, match="outside database transactions"):
        service.prepare_account_key(owner.pk)


def test_restricted_account_cannot_prepare_key(owner):
    User.objects.filter(pk=owner.pk).update(access_status=User.AccessStatus.RESTRICTED)
    with pytest.raises(service.AccountKeyUnavailable):
        service.prepare_account_key(owner.pk)


def test_erase_or_revoke_between_claim_and_finalize_never_installs_active_key(owner, monkeypatch):
    broker = get_broker()
    create = broker.create_dek

    def wrap(user_id, version):
        wrapped = create(user_id, version)
        service.revoke_account_keys(owner.pk, owner)
        return wrapped

    monkeypatch.setattr(broker, "create_dek", wrap)
    monkeypatch.setattr(service, "get_broker", lambda *_: broker)
    with pytest.raises(AccountKeyChanged):
        service.prepare_account_key(owner.pk)
    assert not AccountPiiKey.objects.filter(user=owner, status="active").exists()
