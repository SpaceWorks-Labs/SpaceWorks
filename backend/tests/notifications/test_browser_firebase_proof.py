"""Candidate tests; none have run."""
import pytest
from uuid import uuid4
from django.core.cache import cache
from rest_framework.exceptions import Throttled, ValidationError

from apps.notifications import browser_firebase_challenge as proof
from apps.notifications.models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
from tests.analytics_l25.helpers import manager, space

pytestmark = pytest.mark.django_db
PROJECT = "test-project"
FID = "fid-test-123456789"


def challenge(monkeypatch, actor, makerspace, fid=FID):
    payload = {}
    def capture(settings_row, project, sent_fid, value, nonce):
        payload.update(project=project, fid=sent_fid, challenge=value, nonce=nonce)
    monkeypatch.setattr(proof, "send_challenge", capture)
    response = proof.begin(actor=actor, space=makerspace, project=PROJECT, fid=fid,
                           challenge=str(uuid4()), push_settings=None)
    assert response == {"challenge": payload["challenge"]}
    return payload


def confirm(actor, makerspace, payload, **overrides):
    args = dict(actor=actor, space=makerspace, project=payload["project"], fid=payload["fid"],
                challenge=payload["challenge"], nonce=payload["nonce"])
    args.update(overrides)
    return proof.confirm(**args)


def test_no_registration_until_same_actor_proves_possession(monkeypatch):
    cache.clear()
    makerspace = space()
    owner, attacker = manager(makerspace), manager(makerspace)
    first = challenge(monkeypatch, attacker, makerspace)
    assert not BrowserFirebaseRegistration.objects.exists()
    with pytest.raises(ValidationError):
        confirm(owner, makerspace, first)
    assert not BrowserFirebaseRegistration.objects.exists()
    second = challenge(monkeypatch, owner, makerspace)
    result = confirm(owner, makerspace, second)
    row = BrowserFirebaseRegistration.objects.get(user=owner, makerspace=makerspace, active=True)
    assert row.project_id == PROJECT and row.fid_hmac == proof._mac("fid", PROJECT, FID)
    assert row.fid_ciphertext != FID and row.get_fid() == FID
    assert result["owner_epoch"] == str(BrowserFirebaseInstallation.objects.get(fid_hmac=row.fid_hmac).owner_epoch)
    with pytest.raises(ValidationError):
        confirm(owner, makerspace, second)


def test_proven_switch_revokes_prior_user_only_in_target_space(monkeypatch):
    cache.clear()
    one, two = space(), space()
    first, second = manager(one), manager(one)
    confirm(first, one, challenge(monkeypatch, first, one))
    confirm(first, two, challenge(monkeypatch, first, two))
    confirm(second, one, challenge(monkeypatch, second, one))
    assert not BrowserFirebaseRegistration.objects.get(user=first, makerspace=one).active
    assert BrowserFirebaseRegistration.objects.get(user=first, makerspace=two).active
    assert BrowserFirebaseRegistration.objects.get(user=second, makerspace=one).active


def test_bad_fid_nonce_or_space_cannot_confirm(monkeypatch):
    cache.clear()
    makerspace, other = space(), space()
    actor = manager(makerspace)
    payload = challenge(monkeypatch, actor, makerspace)
    with pytest.raises(ValidationError):
        confirm(actor, makerspace, payload, fid="other-fid-value")
    with pytest.raises(ValidationError):
        confirm(actor, other, payload)
    with pytest.raises(ValidationError):
        confirm(actor, makerspace, payload, nonce="wrong")
    assert not BrowserFirebaseRegistration.objects.exists()


def test_client_challenge_id_is_sent_before_begin_returns(monkeypatch):
    cache.clear()
    makerspace, value = space(), str(uuid4())
    actor = manager(makerspace)
    delivered = []
    monkeypatch.setattr(proof, "send_challenge", lambda _s, _p, _f, challenge, _n: delivered.append(challenge))
    result = proof.begin(actor=actor, space=makerspace, project=PROJECT, fid=FID,
                         challenge=value, push_settings=None)
    assert delivered == [value]
    assert result == {"challenge": value}
    assert FID not in str(cache.get(proof._key("proof", value)))


def test_completed_switch_fences_other_space_delivery(monkeypatch):
    from apps.notifications.browser_firebase_delivery import _deliver
    cache.clear()
    one, two = space(), space()
    first, second = manager(one), manager(one)
    before = confirm(first, two, challenge(monkeypatch, first, two))["owner_epoch"]
    same = confirm(first, one, challenge(monkeypatch, first, one))["owner_epoch"]
    assert before == same
    old = BrowserFirebaseRegistration.objects.get(user=first, makerspace=two)
    from apps.integrations.models_push import PlatformPushSettings
    PlatformPushSettings.objects.create(pk=1, fcm_service_account="configured")
    old.wake_pending_seq = 1
    old.save(update_fields=["wake_pending_seq"])
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.effective", lambda *_: {"configured": True, "config": {"project_id": "test-project"}})
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.module_enabled", lambda *_: True)
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.feature_enabled", lambda *_: True)
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.personal_space", lambda *_: two)
    after = confirm(second, one, challenge(monkeypatch, second, one))["owner_epoch"]
    assert before != after  # An in-flight old hint carries `before` and the new worker rejects it.
    assert BrowserFirebaseInstallation.objects.get(fid_hmac=old.fid_hmac).user_id == second.pk
    called = []
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.send_inbox_hint", lambda *args, **kwargs: called.append(args))
    assert _deliver(old.pk) is False
    assert not called


def test_expiry_and_attempt_limit_fail_closed(monkeypatch):
    cache.clear()
    makerspace = space()
    actor = manager(makerspace)
    payload = challenge(monkeypatch, actor, makerspace)
    for _ in range(5):
        with pytest.raises(ValidationError):
            confirm(actor, makerspace, payload, nonce="wrong")
    with pytest.raises(Throttled):
        confirm(actor, makerspace, payload)
    digest = cache.get(proof._key("proof", payload["challenge"]))
    cache.delete(proof._key("proof", payload["challenge"]))
    for index in range(5):
        cache.delete(proof._key(f"attempt-{index}", digest))
    with pytest.raises(ValidationError):
        confirm(actor, makerspace, payload)
    assert not BrowserFirebaseRegistration.objects.exists()


def test_revoked_registration_never_sends(monkeypatch):
    from apps.notifications.browser_firebase_delivery import _deliver
    cache.clear()
    makerspace = space()
    actor = manager(makerspace)
    confirm(actor, makerspace, challenge(monkeypatch, actor, makerspace))
    row = BrowserFirebaseRegistration.objects.get(user=actor, makerspace=makerspace)
    from apps.integrations.models_push import PlatformPushSettings
    PlatformPushSettings.objects.create(pk=1, fcm_service_account="configured")
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.effective", lambda *_: {"configured": True, "config": {"project_id": "test-project"}})
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.module_enabled", lambda *_: True)
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.feature_enabled", lambda *_: True)
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.personal_space", lambda *_: makerspace)
    row.active = False
    row.wake_pending_seq = 1
    row.save(update_fields=["active", "wake_pending_seq"])
    called = []
    monkeypatch.setattr("apps.notifications.browser_firebase_delivery.send_inbox_hint", lambda *args, **kwargs: called.append(args))
    assert _deliver(row.pk) is False
    assert not called
