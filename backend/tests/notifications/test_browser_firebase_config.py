"""Focused configuration candidate tests, not executed."""
import pytest
import base64
import json
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.urls import reverse

from apps.integrations.firebase_web_config import FirebaseWebWriteSerializer, effective
from apps.integrations.models_push import PlatformPushSettings
from tests.analytics_l25.helpers import client_for, manager, space, superadmin

pytestmark = pytest.mark.django_db


def credential(project):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption()).decode()
    return json.dumps({"project_id": project, "client_email": "test@example.test", "private_key": pem,
                       "token_uri": "https://oauth.example"})


def config():
    point = bytes.fromhex("04" "6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296"
                          "4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5")
    return {"api_key": "AIzaExample", "auth_domain": "example.firebaseapp.com", "project_id": "example-project",
            "app_id": "1:123:web:abc", "messaging_sender_id": "123", "measurement_id": "",
            "vapid_public_key": base64.urlsafe_b64encode(point).decode().rstrip("=")}


def test_config_is_strict_and_never_returns_service_credential(monkeypatch):
    row = PlatformPushSettings.objects.create(pk=1, firebase_web_config=config())
    secret = credential("example-project")
    monkeypatch.setattr(PlatformPushSettings, "get_fcm_service_account", lambda self: secret)
    state = effective(row)
    assert state == {"configured": True, "config": config()}
    assert "PRIVATE KEY" not in str(state)
    extra = {**config(), "service_account": "secret"}
    assert not FirebaseWebWriteSerializer(data={"config": extra}).is_valid()


def test_project_mismatch_and_malformed_config_are_unconfigured(monkeypatch):
    row = PlatformPushSettings.objects.create(pk=1, firebase_web_config=config())
    secret = credential("another-project")
    monkeypatch.setattr(PlatformPushSettings, "get_fcm_service_account", lambda self: secret)
    assert effective(row) == {"configured": False, "config": None}
    row.firebase_web_config = ["invalid"]
    assert effective(row) == {"configured": False, "config": None}


def test_platform_config_is_superadmin_only():
    makerspace = space()
    route = reverse("admin-platform-firebase-web-settings")
    assert client_for(manager(makerspace)).get(route).status_code == 403
    response = client_for(superadmin()).get(route)
    assert response.status_code == 200
    assert response.data == {"configured": False, "config": None}
    assert response["Cache-Control"] == "no-store"


def test_notification_config_is_scoped_and_independent_of_analytics(monkeypatch):
    from tests.events.collab_helpers import client_for as event_client, make_staff
    from tests.events.ticketing_helpers import event_space
    from tests.l2_local.helpers import on
    target = event_space("firebase-config")
    target.enabled_modules = sorted((set(target.enabled_modules) | {"notifications"}) - {"analytics"})
    target.save(update_fields=["enabled_modules"])
    staff = make_staff(target)
    route = f"/api/v1/notifications/browser-firebase/{target.pk}/config"
    assert event_client(staff).get(route).status_code == 404
    on(target, "notifications.web_push")
    row = PlatformPushSettings.objects.create(pk=1, firebase_web_config=config())
    secret = credential("example-project")
    monkeypatch.setattr(PlatformPushSettings, "get_fcm_service_account", lambda self: secret)
    response = event_client(staff).get(route)
    assert response.status_code == 200
    assert response.data == {"configured": True, "config": config()}
    assert response["Cache-Control"] == "no-store"
    row.firebase_web_config = {}
    row.save(update_fields=["firebase_web_config"])
    assert event_client(staff).get(route).data == {"configured": False, "config": None}


def test_resume_requires_current_owner_epoch_and_active_scoped_registration(monkeypatch):
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.notifications.models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
    from apps.notifications.views_browser_firebase_resume import BrowserFirebaseResumeView
    target, other_space = space(), space()
    actor, other = manager(target), manager(target)
    owner = BrowserFirebaseInstallation.objects.create(user=actor, fid_hmac="a" * 64)
    registration = BrowserFirebaseRegistration.objects.create(
        makerspace=target, user=actor, fid_hmac=owner.fid_hmac, fid_ciphertext="ciphertext", project_id="example-project", active=True)
    monkeypatch.setattr(BrowserFirebaseResumeView, "space", lambda self, request, makerspace_id: target if makerspace_id == target.pk else other_space)
    def ask(user, makerspace):
        request = APIRequestFactory().post("/", {"owner_epoch": str(owner.owner_epoch)}, format="json")
        force_authenticate(request, user=user)
        return BrowserFirebaseResumeView.as_view()(request, makerspace_id=makerspace.pk)
    assert ask(actor, target).data == {"may_resume": True}
    assert ask(other, target).data == {"may_resume": False}
    assert ask(actor, other_space).data == {"may_resume": False}
    registration.active = False
    registration.save(update_fields=["active"])
    assert ask(actor, target).data == {"may_resume": False}


def test_global_resume_only_checks_active_actor_and_installation_owner():
    from rest_framework.test import APIRequestFactory, force_authenticate
    from apps.notifications.models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
    from apps.notifications.views_browser_firebase_global_resume import BrowserFirebaseGlobalResumeView
    first, second = space(), space()
    actor, other = manager(first), manager(first)
    owner = BrowserFirebaseInstallation.objects.create(user=actor, fid_hmac="b" * 64)
    for target in (first, second):
        BrowserFirebaseRegistration.objects.create(makerspace=target, user=actor, fid_hmac=owner.fid_hmac,
                                                   fid_ciphertext="encrypted", project_id="example-project", active=True)
    BrowserFirebaseRegistration.objects.filter(makerspace=first).update(active=False)
    def ask(user):
        request = APIRequestFactory().post("/", {"owner_epoch": str(owner.owner_epoch)}, format="json")
        force_authenticate(request, user=user)
        return BrowserFirebaseGlobalResumeView.as_view()(request)
    assert ask(actor).data == {"may_resume": True}
    assert ask(other).data == {"may_resume": False}
    actor.is_active = False
    assert ask(actor).data == {"may_resume": False}


def test_resume_read_budget_does_not_consume_challenge_budget():
    from types import SimpleNamespace
    from django.core.cache import cache
    from apps.notifications.browser_firebase_throttles import BrowserFirebaseReadThrottle
    from apps.notifications.views_browser_firebase import FirebaseThrottle
    actor = manager(space())
    request = SimpleNamespace(user=actor)
    cache.delete(BrowserFirebaseReadThrottle().get_cache_key(request, None))
    cache.delete(FirebaseThrottle().get_cache_key(request, None))
    assert all(BrowserFirebaseReadThrottle().allow_request(request, None) for _ in range(120))
    assert not BrowserFirebaseReadThrottle().allow_request(request, None)
    assert all(FirebaseThrottle().allow_request(request, None) for _ in range(10))
    assert not FirebaseThrottle().allow_request(request, None)
