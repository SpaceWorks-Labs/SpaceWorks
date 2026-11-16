"""Browser-push contracts: tenant standing, possession proof, native exclusion, global reads."""
from uuid import uuid4

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.integrations.models_push import PlatformPushSettings
from apps.notifications import browser_firebase_challenge as proof
from apps.notifications.browser_alerts import endpoint_hash
from apps.notifications.models_browser_alerts import BrowserAlertSubscription
from apps.notifications.models_browser_firebase import BrowserFirebaseInstallation, BrowserFirebaseRegistration
from tests.notifications.routes_support_cx11b_g6 import cycle, hidden, send, world
from tests.notifications.test_browser_firebase_config import config, credential
from tests.notifications.test_object_switches_cx11b_p2 import personal_client

pytestmark = [pytest.mark.django_db, pytest.mark.area_notifications]
KEYS = ["notifications", "notifications.member_inbox", "notifications.web_push"]
ENDPOINT = "https://fcm.googleapis.com/fcm/send/g6-private-endpoint"
FID = "g6-firebase-installation"


def vapid(settings):
    settings.WEB_PUSH_VAPID_PRIVATE_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAE"
    settings.WEB_PUSH_VAPID_SUBJECT = "mailto:g6@example.test"


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("method", ["get", "post", "delete"])
@pytest.mark.parametrize("key", KEYS)
def test_web_push_subscription_saves_revokes_or_counts_only_owner(method, key, native, settings, monkeypatch):
    vapid(settings)
    space, actor, client, stranger, foreign = world(native)
    now = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: now)
    row = BrowserAlertSubscription(makerspace=space, user=actor, endpoint_sha256=endpoint_hash(ENDPOINT), p256dh="a" * 87)
    row.set_secrets(ENDPOINT, "b" * 22)
    row.revoked_at = now if method == "post" else None
    row.save()
    url = f"/api/v1/notifications/browser-alerts/{space.pk}"
    body = {"endpoint": ENDPOINT, "keys": {"p256dh": "c" * 87, "auth": "d" * 22}}
    def check(response):
        row.refresh_from_db()
        assert response.data == {"subscribed_browsers": 0 if method == "delete" else 1}
        assert row.user_id == actor.pk
        assert row.revoked_at == (now if method == "delete" else None)
        assert BrowserAlertSubscription.objects.count() == 1
        if method == "post":
            assert (row.get_endpoint(), row.get_auth_secret(), row.p256dh) == (ENDPOINT, "d" * 22, "c" * 87)
            assert row.endpoint != ENDPOINT and row.auth_secret != "d" * 22
    actions = () if method == "get" else ("notification.browser_alert_subscribed" if method == "post"
        else "notification.browser_alert_unsubscribed",)
    cycle(space, key, lambda: send(client, method, url, body), check, actions=actions,
          off=(404, "module_disabled" if key == "notifications" else
               "feature_disabled" if key == "notifications.member_inbox" else "not_found"),
          probes=[hidden(lambda: send(foreign, method, url, body), native_staff=native)])


@pytest.mark.parametrize("operation", ["config", "resume", "begin", "confirm", "delete"])
@pytest.mark.parametrize("key", KEYS)
def test_firebase_route_real_proof_and_native_refusal(operation, key, monkeypatch):
    space, actor, client, stranger, foreign = world(False)
    platform = PlatformPushSettings.objects.create(pk=1, firebase_web_config=config())
    platform.set_fcm_service_account(credential("example-project"))
    platform.save(update_fields=["fcm_service_account"])
    identity = proof._mac("fid", "example-project", FID)
    owner = BrowserFirebaseInstallation.objects.create(user=actor, fid_hmac=identity)
    row = BrowserFirebaseRegistration(makerspace=space, user=actor, project_id="example-project",
        fid_hmac=identity, active=operation != "confirm")
    row.set_fid(FID)
    row.save()
    deliveries = []
    monkeypatch.setattr(proof, "send_challenge", lambda _s, project, fid, challenge, nonce:
        deliveries.append((project, fid, challenge, nonce)))
    suffix = {"config": "config", "resume": "may-resume", "begin": "challenge", "confirm": "confirm", "delete": "challenge"}[operation]
    method = "get" if operation == "config" else "delete" if operation == "delete" else "post"
    url = f"/api/v1/notifications/browser-firebase/{space.pk}/{suffix}"
    body = {"project_id": "example-project", "fid": FID}
    if operation == "resume":
        body = {"owner_epoch": str(owner.owner_epoch)}
    if operation == "begin":
        body["challenge_id"] = str(uuid4())
    def prepare():
        if operation == "confirm":
            proof.begin(actor=actor, space=space, project="example-project", fid=FID,
                        challenge=str(uuid4()), push_settings=platform)
            project, fid, challenge, nonce = deliveries[-1]
            body.update(project_id=project, fid=fid, challenge=challenge, nonce=nonce)
    def check(response):
        row.refresh_from_db()
        if operation == "config":
            assert response.data == {"configured": True, "config": config()}
        elif operation == "resume":
            assert response.data == {"may_resume": True}
        elif operation == "begin":
            project, fid, challenge, nonce = deliveries[-1]
            assert (project, fid, challenge) == ("example-project", FID, body["challenge_id"])
            assert response.data == {"challenge": challenge}
            assert cache.get(proof._key("proof", challenge)) == proof._mac(
                "proof", challenge, nonce, actor.pk, space.pk, project, fid)
        elif operation == "confirm":
            assert response.data == {"owner_epoch": str(owner.owner_epoch)}
            assert row.active and row.revoked_at is None
            assert row.confirmed_at is not None and row.get_fid() == FID
            assert row.fid_ciphertext != FID
            assert BrowserFirebaseRegistration.objects.count() == 1
        else:
            assert row.active is False and row.revoked_at is not None
    native = personal_client(actor, space, True)
    actions = {"begin": ("notification.browser_firebase_challenge_started",),
               "confirm": ("notification.browser_firebase_subscribed",),
               "delete": ("notification.browser_firebase_unsubscribed",)}.get(operation, ())
    cycle(space, key, lambda: send(client, method, url, body), check, prepare=prepare,
          on=(204 if operation == "delete" else 200, None), actions=actions,
          off=(404, "module_disabled" if key == "notifications" else
               "feature_disabled" if key == "notifications.member_inbox" else "not_found"),
          probes=[hidden(lambda: send(foreign, method, url, body)),
                  (lambda: send(native, method, url, body), (403, "permission_denied"), (403, "permission_denied"))])


@pytest.mark.parametrize("key", KEYS)
@pytest.mark.parametrize("operation", ["key", "global-resume"])
def test_global_browser_metadata_has_no_tenant_switch_or_membership_gate(operation, key, settings):
    vapid(settings)
    space, actor, client, stranger, foreign = world(False)
    owner = BrowserFirebaseInstallation.objects.create(user=actor, fid_hmac="e" * 64)
    url = "/api/v1/notifications/" + ("browser-alerts/key" if operation == "key" else "browser-firebase/may-resume")
    method = "get" if operation == "key" else "post"
    body = {} if operation == "key" else {"owner_epoch": str(owner.owner_epoch)}
    expected = {"configured": True, "public_key": config()["vapid_public_key"]} if operation == "key" else {"may_resume": True}
    def check(response):
        assert response.data == expected
    # Global resume is owner scoped; a foreign browser gets False, never the epoch owner's identity.
    def foreign_read():
        response = send(foreign, method, url, body)
        assert response.data == (expected if operation == "key" else {"may_resume": False})
        return response
    native = personal_client(actor, space, True)
    # This metadata is global; a native grant may call it without a tenant selector.
    # A selected grant retains authentication's 403 for unresolved global targets (494).
    if operation == "key":
        native._credentials.pop("HTTP_X_MAKERSPACE_ID")
    native_pair = (200, None) if operation == "key" else (403, "permission_denied")
    cycle(space, key, lambda: send(client, method, url, body), check, off=(200, None), off_check=check,
          probes=[(foreign_read, (200, None), (200, None)),
                  (lambda: send(native, method, url, body), native_pair, native_pair)])
