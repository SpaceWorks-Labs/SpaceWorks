"""Durable wake-up regression candidates; no provider connection."""
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db.models import F

from apps.integrations.models_push import PlatformPushSettings
from apps.notifications import browser_firebase_delivery as delivery
from apps.notifications.models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
from tests.analytics_l25.helpers import manager, space


@pytest.mark.django_db(transaction=True)
def test_full_eager_inbox_commit_persists_without_calling_provider(monkeypatch, settings):
    from apps.notifications.inbox import write_envelope_inbox
    target = space()
    actor = manager(target)
    settings.SPACEWORKS_DEPLOYMENT_PROFILE = "full"
    settings.CLOUD_TASK_PROFILE = "redis"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    PlatformPushSettings.objects.create(pk=1, fcm_service_account="configured")
    registration = BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, project_id="test-project", fid_hmac="a" * 64,
        fid_ciphertext="encrypted", active=True)
    monkeypatch.setattr(delivery, "effective", lambda *_: {"configured": True, "config": {"project_id": "test-project"}})
    monkeypatch.setattr(delivery, "module_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "feature_enabled", lambda *_: True)
    calls = []
    monkeypatch.setattr(delivery, "send_inbox_hint", lambda *a, **k: calls.append("provider"))
    monkeypatch.setattr(delivery.deliver_registration, "delay", lambda *a, **k: calls.append("delay"))
    monkeypatch.setattr("apps.notifications.browser_alerts.enqueue", lambda *_: None)
    monkeypatch.setattr("apps.notifications.inbox._hint", lambda *_: None)
    envelope = SimpleNamespace(scope={}, audience="staff", makerspace_id=target.pk, recipient_id=actor.pk,
                               dedup_key=str(uuid4()), feature="test", event="created")
    write_envelope_inbox(envelope, {"subject": "test", "text": "test", "link": "/"})
    registration.refresh_from_db()
    assert registration.wake_pending_seq == 1 and registration.wake_sent_seq == 0
    assert calls == []


@pytest.mark.django_db(transaction=True)
def test_new_wakeup_during_send_is_not_lost(monkeypatch):
    target = space()
    actor = manager(target)
    config = PlatformPushSettings.objects.create(pk=1, fcm_service_account="configured")
    BrowserFirebaseInstallation.objects.create(user=actor, fid_hmac="b" * 64)
    row = BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, project_id="test-project", fid_hmac="b" * 64,
        fid_ciphertext="encrypted", active=True, wake_pending_seq=1)
    monkeypatch.setattr(delivery, "effective", lambda *_: {"configured": True, "config": {"project_id": "test-project"}})
    monkeypatch.setattr(delivery, "module_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "feature_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "personal_space", lambda *_: target)
    monkeypatch.setattr(BrowserFirebaseRegistration, "get_fid", lambda self: "fid")
    def send(*args, **kwargs):
        BrowserFirebaseRegistration.objects.filter(pk=row.pk).update(wake_pending_seq=F("wake_pending_seq") + 1)
    monkeypatch.setattr(delivery, "send_inbox_hint", send)
    assert delivery._deliver(row.pk) is True
    row.refresh_from_db()
    assert row.wake_pending_seq == 2 and row.wake_sent_seq == 1

@pytest.mark.django_db(transaction=True)
def test_eager_recovery_advances_past_denied_and_wraps(monkeypatch, settings):
    from django.core.cache import cache
    from rest_framework.exceptions import PermissionDenied
    cache.delete("browser_firebase_wakeup_scan_cursor")
    settings.CELERY_TASK_ALWAYS_EAGER = True
    target = space()
    actor = manager(target)
    rows = [BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, project_id="test-project", fid_hmac=char * 64,
        fid_ciphertext="encrypted", active=True, wake_pending_seq=1) for char in ("c", "d")]
    seen = []
    def attempt(pk):
        seen.append(pk)
        if pk == rows[0].pk:
            raise PermissionDenied()
    monkeypatch.setattr(delivery, "_deliver", attempt)
    delivery.sweep_pending()
    delivery.sweep_pending()
    delivery.sweep_pending()
    assert seen == [rows[0].pk, rows[1].pk, rows[0].pk]
    rows[0].refresh_from_db()
    assert rows[0].wake_pending_seq == 1 and rows[0].wake_sent_seq == 0


@pytest.mark.django_db(transaction=True)
def test_free_chunk_advances_past_denied_item(monkeypatch):
    target = space()
    actor = manager(target)
    rows = [BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, project_id="test-project", fid_hmac=char * 64,
        fid_ciphertext="encrypted", active=True, wake_pending_seq=1) for char in ("e", "f")]
    seen = []
    monkeypatch.setattr(delivery, "_deliver", lambda pk, **kwargs: seen.append(pk) or False)
    context = SimpleNamespace(check=lambda: None)
    first = delivery.drain_chunk(context, 0)
    second = delivery.drain_chunk(context, first["cursor"])
    assert seen == [rows[0].pk, rows[1].pk]
    assert first["remaining"] and not second["remaining"] and second["cursor"] == 0

@pytest.mark.django_db(transaction=True)
def test_cleared_web_config_blocks_enqueue_send_and_enrollment(monkeypatch):
    from rest_framework.exceptions import NotFound
    from apps.notifications.views_browser_firebase import BrowserFirebaseBeginView
    target = space()
    actor = manager(target)
    config = PlatformPushSettings.objects.create(pk=1, fcm_service_account="native-credentials", firebase_web_config={})
    row = BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, project_id="test-project", fid_hmac="7" * 64,
        fid_ciphertext="encrypted", active=True, wake_pending_seq=1)
    monkeypatch.setattr(delivery, "module_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "feature_enabled", lambda *_: True)
    sent = []
    monkeypatch.setattr(delivery, "send_inbox_hint", lambda *a, **k: sent.append("send"))
    monkeypatch.setattr("apps.notifications.views_browser_firebase.proof.begin", lambda **kwargs: sent.append("begin"))
    inbox = SimpleNamespace(makerspace=target, makerspace_id=target.pk, user_id=actor.pk)
    assert delivery.mark_pending(inbox) == []
    assert delivery._deliver(row.pk) is False
    view = BrowserFirebaseBeginView()
    monkeypatch.setattr(view, "space", lambda *_: target)
    request = SimpleNamespace(user=actor, data={"project_id": "test-project", "fid": "fid-test-123456789",
                                                "challenge_id": str(uuid4())})
    with pytest.raises(NotFound):
        view.post(request, target.pk)
    row.refresh_from_db()
    config.refresh_from_db()
    assert row.wake_pending_seq == 1 and row.wake_sent_seq == 0
    assert config.fcm_service_account == "native-credentials" and sent == []


@pytest.mark.django_db(transaction=True)
def test_begin_api_audits_success_without_challenge_secrets(monkeypatch):
    from apps.audit.models import AuditLog
    from apps.notifications.views_browser_firebase import BrowserFirebaseBeginView
    target = space()
    actor = manager(target)
    PlatformPushSettings.objects.create(pk=1, fcm_service_account="native-credentials")
    monkeypatch.setattr("apps.notifications.views_browser_firebase.effective",
                        lambda _: {"configured": True, "config": {"project_id": "test-project"}})
    challenge_id = str(uuid4())
    fid = "private-fid-123456789"
    nonce = "private-nonce-sentinel"
    monkeypatch.setattr("apps.notifications.views_browser_firebase.proof.begin",
                        lambda **kwargs: {"challenge": kwargs["challenge"]})
    view = BrowserFirebaseBeginView()
    monkeypatch.setattr(view, "space", lambda *_: target)
    response = view.post(SimpleNamespace(user=actor, data={"project_id": "test-project", "fid": fid,
                                                          "challenge_id": challenge_id}), target.pk)
    assert response.status_code == 200
    entries = AuditLog.objects.filter(action="notification.browser_firebase_challenge_started")
    assert entries.count() == 1
    entry = entries.get()
    assert entry.actor_id == actor.pk and entry.makerspace_id == target.pk
    assert entry.target_id == str(target.pk) and entry.meta == {}
    for secret in (fid, nonce, challenge_id, "test-project"):
        assert secret not in str(entry.meta)


def test_firebase_unregistered_response_is_permanent(monkeypatch):
    from apps.integrations import push_firebase_browser as provider
    from apps.integrations.push_fcm import PushProviderError
    monkeypatch.setattr(provider, "fcm_access_token", lambda *a, **k: ("access", "test-project"))
    response = SimpleNamespace(status_code=404, json=lambda: {"error": {"details": [
        {"errorCode": "UNREGISTERED"}]}})
    monkeypatch.setattr(provider.requests, "post", lambda *a, **k: response)
    with pytest.raises(PushProviderError) as raised:
        provider.send_inbox_hint(None, "test-project", "fid", "epoch")
    assert raised.value.invalid_token is True


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("permanent", [True, False])
def test_provider_failure_revokes_only_permanent_registration(monkeypatch, permanent):
    from apps.integrations.push_fcm import PushProviderError
    target = space()
    actor = manager(target)
    PlatformPushSettings.objects.create(pk=1, fcm_service_account="configured")
    owner = BrowserFirebaseInstallation.objects.create(user=actor, fid_hmac="8" * 64)
    row = BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, project_id="test-project", fid_hmac="8" * 64,
        fid_ciphertext="encrypted", active=True, wake_pending_seq=1)
    monkeypatch.setattr(delivery, "effective", lambda *_: {"configured": True, "config": {"project_id": "test-project"}})
    monkeypatch.setattr(delivery, "module_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "feature_enabled", lambda *_: True)
    monkeypatch.setattr(delivery, "personal_space", lambda *_: target)
    monkeypatch.setattr(BrowserFirebaseRegistration, "get_fid", lambda self: "fid")
    def fail(*args, **kwargs):
        raise PushProviderError("provider failure", invalid_token=permanent)
    monkeypatch.setattr(delivery, "send_inbox_hint", fail)
    epoch = owner.owner_epoch
    assert delivery._deliver(row.pk) is False
    row.refresh_from_db()
    owner.refresh_from_db()
    assert owner.owner_epoch == epoch and owner.user_id == actor.pk
    assert row.active is not permanent
    assert (row.revoked_at is not None) is permanent
    assert (row.wake_retry_at is None) is permanent
    assert row.wake_sent_seq == 0
