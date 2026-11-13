"""Shared Phase 1b setup using the existing inbox and native-device helpers."""

import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from apps.integrations.models import NotificationPreference, PlatformPushSettings, PushDevice
from apps.integrations.notification_enums import NotificationChannel
from apps.integrations.notify import LifecyclePayload
from apps.notifications.inbox import InboxDelivery, write_matrix_inbox
from apps.notifications.models import NotificationInboxRow
from tests.return_helpers import make_space
from django.utils import timezone
from apps.accounts.models import DeviceGrant
from tests.device_helpers import make_native_app_registration
from tests.test_personal_inbox_f2 import enable, member


@pytest.fixture
def push_case(settings, monkeypatch, django_capture_on_commit_callbacks, request):
    """Capture queue publication and HTTP, retaining real policy and transport code."""
    settings.PUSH_TOKEN_HMAC_KEY = "h" * 64
    space = make_space("m1b-push")
    # `mobile.push` is a child of the `mobile` module (which needs member accounts);
    # without it no canonical native_push leg resolves and no staff fan-out runs.
    space.enabled_modules = sorted({*space.enabled_modules, "notifications", "bookings",
                                    "member_accounts", "mobile"})
    space.save(update_fields=["enabled_modules"])
    enable(space)
    space.enabled_features = sorted({*space.enabled_features, "mobile.push"})
    space.save(update_fields=["enabled_features"])
    user = member("m1b-owner", space)
    provider = getattr(request, "param", "fcm")
    assert user.account_kind == "member"
    native_platform = "android" if provider == "fcm" else "apple"
    now = timezone.now()
    grant = DeviceGrant.objects.create(
        user=user, registration=make_native_app_registration(platform=native_platform),
        authority="member", platform=native_platform, app_id="org.spaceworks.app",
        signing_identity="TEAM.org.spaceworks.app", environment="development",
        attested_at=now, last_used_at=now, attestation_subject_fingerprint="f" * 64,
        credential_generation=user.credential_generation, login_method="password",
    )
    device = PushDevice(
        user=user, makerspace=space, device_grant=grant, provider=provider,
        environment="development", token_fingerprint="d" * 64,
    )
    device.set_token("m1b-device-token")
    device.save()
    platform = PlatformPushSettings.load()
    platform.set_fcm_service_account(json.dumps({
        "client_email": "push@example.test", "private_key": "test-key",
        "token_uri": "https://oauth.example.test/token", "project_id": "m1b-project",
    }))
    platform.set_apns_private_key("test-apns-key")
    platform.apns_team_id, platform.apns_key_id = "TEAM", "KEY"
    platform.apns_topic = "org.spaceworks.app"
    platform.save()
    # Signing is outside this transport contract; all HTTP still traverses the adapters.
    monkeypatch.setattr("apps.integrations.push_fcm.jwt.encode", lambda *a, **kw: "signed-jwt")
    for channel in NotificationChannel.values:
        NotificationPreference.objects.create(
            makerspace=space, feature="bookings", channel=channel,
            enabled=channel in {"in_app", "native_push"},
        )
    queued = Mock()
    monkeypatch.setattr("apps.notifications.tasks.deliver_member_push.delay", queued)
    monkeypatch.setattr("apps.notifications.inbox._hint", Mock())
    case = SimpleNamespace(
        space=space, user=user, grant=grant, device=device, platform=platform,
        queued=queued, calls=[], oauth_calls=[], status=200, error={}, before_http=None,
        summary="Your booking is confirmed. " * 12,
        staff_text="STAFF PRIVATE DETAIL: never send this to the member",
    )

    def response(status, payload):
        return SimpleNamespace(status_code=status, json=lambda: payload)

    def record(url, **kwargs):
        if case.before_http:
            case.before_http()
        case.calls.append({"url": url, **kwargs})
        return response(case.status, case.error)

    def post(url, **kwargs):
        if url == "https://oauth.example.test/token":
            case.oauth_calls.append(kwargs)
            return response(200, {"access_token": "oauth-test-token"})
        return record(url, **kwargs)

    class APNsClient:
        def __init__(self, **kwargs):
            assert kwargs == {"http2": True, "timeout": 10}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, **kwargs):
            return record(url, **kwargs)

    monkeypatch.setattr("apps.integrations.push_fcm.requests.post", post)
    monkeypatch.setattr("apps.integrations.push_apns.httpx.Client", APNsClient)

    def enqueue(*, payload=None, event_key=None):
        key = event_key or uuid4()
        payload = payload or LifecyclePayload(
            text=case.staff_text, staff_channels_enabled=False,
            inbox=(InboxDelivery(user.pk, "Your booking", case.summary,
                                 f"/m/{space.slug}/member"),),
        )
        with django_capture_on_commit_callbacks(execute=True):
            write_matrix_inbox(space, "bookings", "confirmed", payload, key)
        return NotificationInboxRow.objects.filter(makerspace=space, user=user, event_key=key).first()

    case.enqueue = enqueue
    from tests.notifications.push_envelope_helpers import install_envelopes
    install_envelopes(case, monkeypatch, django_capture_on_commit_callbacks)
    return case


def wire_message(case, index=0):
    """Normalize only the provider envelope; assertions still inspect the wire payload."""
    payload = case.calls[index]["json"]
    if case.device.provider == "fcm":
        return payload["message"]["notification"], payload["message"]["data"]
    return payload["aps"]["alert"], payload["data"]
