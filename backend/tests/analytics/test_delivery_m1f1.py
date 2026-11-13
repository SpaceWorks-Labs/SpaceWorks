import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from apps.integrations.dispatch import dispatch_email
from apps.integrations.models import EmailLog, PushDevice, NotificationDeliveryLog
from apps.integrations.models_tracking import EmailProviderEvent, PushDeliveryAttempt
from apps.integrations.push import deliver_native_push
from apps.integrations.push_fcm import PushProviderError
from apps.notifications.models_push import MemberPushDelivery
from tests.return_helpers import make_member, make_space
from tests.test_bounce_ingestion import setup, deliver
from tests.accounts.account_factories import device_grant
from tests.notifications.test_support_m1b import push_case  # noqa: F401

pytestmark = pytest.mark.django_db


def test_staff_push_retry_records_each_device_once_and_keeps_success(monkeypatch):
    space = make_space("staff-attempt")
    user = make_member("staff-attempt-user", space)
    grant = device_grant(user, platform="android")
    devices = [PushDevice.objects.create(user=user, makerspace=space, device_grant=grant,
        provider="fcm", environment="development", token_fingerprint=str(i), token_ciphertext="unused") for i in range(2)]
    log = NotificationDeliveryLog.objects.create(makerspace=space, channel="native_push", feature="hardware_requests", event="submitted")
    monkeypatch.setattr("apps.makerspaces.platform.feature_enabled", lambda *a: True)
    monkeypatch.setattr("apps.integrations.push.PlatformPushSettings.load", lambda: SimpleNamespace(fcm_configured=True, apns_configured=False))
    monkeypatch.setattr("apps.integrations.push.staff_user_ids_for_feature", lambda *a, **k: [user.pk])
    monkeypatch.setattr("apps.notifications.preferences.personal_enabled", lambda *a, **k: True)
    sent = []

    def provider(config, device, *args):
        sent.append(device.pk)
        if device.pk == devices[1].pk and sent.count(device.pk) == 1:
            raise PushProviderError("private provider response")
        return True

    monkeypatch.setattr("apps.integrations.push.send_device_push", provider)
    with pytest.raises(PushProviderError):
        deliver_native_push(log)
    deliver_native_push(log)
    assert sent.count(devices[0].pk) == 1 and sent.count(devices[1].pk) == 2
    rows = list(PushDeliveryAttempt.objects.order_by("push_device_id"))
    assert len(rows) == 2
    assert [r.attempts for r in rows] == [1, 2]
    assert all(r.status == "sent" and r.sent_at and r.platform == "android" and r.provider_source == "platform" for r in rows)
    assert all("private" not in r.last_error for r in rows)


def test_member_push_children_record_device_metadata_once_under_claim_fencing(push_case):
    """Canonical envelope children carry per-device platform/source facts; a repeat
    send of a settled parent neither re-claims the child nor calls the provider."""
    from apps.notifications.member_push import send_envelope_push
    parent = push_case.prepare()
    assert send_envelope_push(parent, push_case.rendered).accepted
    assert send_envelope_push(parent, push_case.rendered).accepted
    delivery = MemberPushDelivery.objects.get(envelope_delivery=parent)
    assert (delivery.platform, delivery.provider_source, delivery.status, delivery.attempts) == (
        "android", "platform", "sent", 1)
    assert delivery.lease_token is None and delivery.lease_until is None
    assert len(push_case.calls) == 1


def test_staff_invalid_tokens_are_terminal_private_outcomes(monkeypatch):
    space = make_space("staff-invalid-attempt")
    user = make_member("staff-invalid-user", space)
    grant = device_grant(user, platform="android")
    device = PushDevice.objects.create(user=user, makerspace=space, device_grant=grant,
        provider="fcm", environment="development", token_fingerprint="invalid", token_ciphertext="unused")
    log = NotificationDeliveryLog.objects.create(makerspace=space, channel="native_push", feature="hardware_requests", event="submitted")
    monkeypatch.setattr("apps.makerspaces.platform.feature_enabled", lambda *a: True)
    monkeypatch.setattr("apps.integrations.push.PlatformPushSettings.load", lambda: SimpleNamespace(fcm_configured=True, apns_configured=False))
    monkeypatch.setattr("apps.integrations.push.staff_user_ids_for_feature", lambda *a, **k: [user.pk])
    monkeypatch.setattr("apps.notifications.preferences.personal_enabled", lambda *a, **k: True)
    monkeypatch.setattr("apps.integrations.push.send_device_push", Mock(side_effect=PushProviderError("secret token", invalid_token=True)))
    assert deliver_native_push(log)
    row = PushDeliveryAttempt.objects.get()
    device.refresh_from_db()
    assert row.status == "failed" and row.last_error == "invalid_token" and row.sent_at is None
    assert row.recipient_id == user.pk and not device.active


@pytest.mark.parametrize("own", [True, False])
def test_email_source_is_actual_connection_including_platform_fallback(own, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    space = make_space("email-own" if own else "email-fallback")
    if own:
        space.smtp_host = "smtp.example.com"
        space.smtp_port = 587
        space.save(update_fields=["smtp_host", "smtp_port"])
        # Parity E-B8: a space's own SMTP is used only after its test message was accepted.
        from django.utils import timezone
        from apps.integrations.space_smtp_gate import mark_verified
        mark_verified(space, timezone.now())
    from unittest.mock import patch
    with patch("apps.integrations.email.validate_smtp_endpoint"):
        log = dispatch_email(makerspace=space, to_email="member@example.test", subject="Status", text_body="Status", sync=True)
    assert log.status == "sent"
    assert log.provider_source == ("own" if own else "platform")
    assert log.provider_message_id == ""


def test_provider_returned_message_id_is_stored(monkeypatch, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    def send(message):
        message.provider_message_id = "provider-message-123"
        return 1
    monkeypatch.setattr("apps.integrations.dispatch_delivery.EmailMultiAlternatives.send", send)
    log = dispatch_email(to_email="member@example.test", subject="Status", text_body="Status", makerspace=None, sync=True)
    assert log.provider_message_id == "provider-message-123" and log.provider_source == "platform"


def test_bounce_exact_correlation_tenant_dedupe_and_complaints():
    space = setup()
    other = make_space("bounce-other-m1f1")
    log = EmailLog.objects.create(makerspace=space, provider_message_id="message-1", to_email="member@example.test", subject="x")
    foreign = EmailLog.objects.create(makerspace=other, provider_message_id="message-1", to_email="member@example.test", subject="x")
    unrelated = EmailLog.objects.create(makerspace=space, provider_message_id="message-2", to_email="member@example.test", subject="x")
    def event(event_id, message_id, reason="bounce"):
        return deliver(space, body=json.dumps({"event_id": event_id, "address": "member@example.test", "message_id": message_id, "reason": reason}))
    assert event("event-1", "message-1").status_code == 200
    log.refresh_from_db()
    stamped = log.bounced_at
    assert stamped and log.complained_at is None
    assert event("event-1", "message-2", "complaint").status_code == 200
    log.refresh_from_db(); foreign.refresh_from_db(); unrelated.refresh_from_db()
    assert log.bounced_at == stamped and foreign.bounced_at is None and unrelated.complained_at is None
    assert event("event-2", "message-1", "complaint").status_code == 200
    log.refresh_from_db()
    assert log.complained_at and log.bounced_at == stamped
    assert event("event-3", "missing").status_code == 200
    assert EmailProviderEvent.objects.filter(makerspace=space).count() == 3
