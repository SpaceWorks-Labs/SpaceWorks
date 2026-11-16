"""Decision 337d: the FCM installation row lock is not held across the provider call (claim/lease, like the push)."""
from uuid import uuid4

import pytest
from django.db import connection

from apps.integrations.models_push import PlatformPushSettings
from apps.notifications import browser_firebase_delivery as delivery
from apps.notifications.models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
from tests.analytics_l25.helpers import manager, space

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def case(monkeypatch):
    target = space()
    actor = manager(target)
    PlatformPushSettings.objects.create(pk=1, fcm_service_account="configured")
    owner = BrowserFirebaseInstallation.objects.create(user=actor, fid_hmac="c" * 64)
    row = BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, project_id="test-project", fid_hmac="c" * 64,
        fid_ciphertext="encrypted", active=True, wake_pending_seq=1)
    monkeypatch.setattr(delivery, "effective", lambda *_: {"configured": True, "config": {"project_id": "test-project"}})
    monkeypatch.setattr(delivery, "module_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "feature_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "personal_space", lambda *_: target)
    monkeypatch.setattr(BrowserFirebaseRegistration, "get_fid", lambda self: "fid")
    return {"row": row, "owner": owner}


def test_the_provider_is_called_outside_any_transaction_and_a_second_worker_is_kept_off(monkeypatch, case):
    row, seen = case["row"], {}

    def send(*args, **kwargs):
        seen["atomic"] = connection.in_atomic_block
        seen["second_worker"] = delivery._deliver(row.pk)  # claimed: the registration is not sent twice

    monkeypatch.setattr(delivery, "send_inbox_hint", send)
    assert delivery._deliver(row.pk) is True
    assert seen == {"atomic": False, "second_worker": False}
    row.refresh_from_db()
    assert row.wake_sent_seq == 1 and row.wake_retry_at is None


def test_an_installation_that_changed_hands_during_the_send_stays_pending(monkeypatch, case):
    row = case["row"]

    def send(*args, **kwargs):
        BrowserFirebaseInstallation.objects.filter(pk=case["owner"].pk).update(owner_epoch=uuid4())

    monkeypatch.setattr(delivery, "send_inbox_hint", send)
    assert delivery._deliver(row.pk) is False
    row.refresh_from_db()
    assert row.wake_sent_seq == 0 and row.wake_pending_seq == 1 and row.wake_retry_at is None


def test_a_dead_worker_claim_expires_and_a_provider_failure_backs_off(monkeypatch, case):
    from datetime import timedelta
    from django.utils import timezone
    from apps.integrations.push_fcm import PushProviderError
    row = case["row"]
    BrowserFirebaseRegistration.objects.filter(pk=row.pk).update(wake_retry_at=timezone.now() + timedelta(seconds=90))
    monkeypatch.setattr(delivery, "send_inbox_hint", lambda *a, **k: pytest.fail("a live claim must not be sent"))
    assert delivery._deliver(row.pk) is False
    BrowserFirebaseRegistration.objects.filter(pk=row.pk).update(wake_retry_at=timezone.now() - timedelta(seconds=1))

    def fail(*args, **kwargs):
        raise PushProviderError("down")

    monkeypatch.setattr(delivery, "send_inbox_hint", fail)
    assert delivery._deliver(row.pk) is False
    row.refresh_from_db()
    assert row.wake_retry_at > timezone.now() and row.wake_sent_seq == 0
