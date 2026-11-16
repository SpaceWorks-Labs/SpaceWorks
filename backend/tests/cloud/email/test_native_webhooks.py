import base64
import hashlib
import hmac
import json
import time

import pytest

from apps.integrations.mail_providers.webhook_signatures import MailEvent, verify


def resend_request(body=None, *, stamp=None):
    key = b"0123456789abcdef0123456789abcdef"
    raw = json.dumps(body or {"type": "email.bounced", "data": {"email_id": "opaque-id"}}).encode()
    stamp = str(int(time.time())) if stamp is None else stamp
    signed = b"event-id." + stamp.encode() + b"." + raw
    headers = {"svix-id": "event-id", "svix-timestamp": stamp,
               "svix-signature": "v1," + base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()}
    return raw, headers, {"webhook_secret": "whsec_" + base64.b64encode(key).decode()}


def test_resend_signature_verifies_exact_raw_bytes_and_supports_rotation_headers():
    raw, headers, credentials = resend_request()
    headers["svix-signature"] = "v1,oldsignature " + headers["svix-signature"]
    assert verify("resend", raw, headers, credentials) == MailEvent("event-id", "opaque-id", "bounce")
    with pytest.raises(ValueError):
        verify("resend", raw + b" ", headers, credentials)


@pytest.mark.parametrize("stamp", ["123", "not-a-number", "１２３"])
def test_stale_or_non_ascii_resend_timestamp_cannot_mutate(stamp):
    raw, headers, credentials = resend_request(stamp=stamp)
    with pytest.raises(ValueError):
        verify("resend", raw, headers, credentials)


def test_mailgun_signed_json_only_maps_permanent_failures():
    stamp = str(int(time.time()))
    key, token = "signing-key", "random-token"
    signature = hmac.new(key.encode(), (stamp + token).encode(), hashlib.sha256).hexdigest()
    body = {"signature": {"timestamp": stamp, "token": token, "signature": signature},
            "event-data": {"id": "event", "event": "failed", "severity": "permanent",
                           "message": {"headers": {"message-id": "message"}}}}
    credentials = {"webhook_signing_key": key}
    assert verify("mailgun", json.dumps(body).encode(), {}, credentials).status == "bounce"
    body["event-data"]["severity"] = "temporary"
    assert verify("mailgun", json.dumps(body).encode(), {}, credentials).status is None
    body["signature"]["signature"] = "forged"
    with pytest.raises(ValueError):
        verify("mailgun", json.dumps(body).encode(), {}, credentials)


@pytest.mark.django_db
def test_native_callback_replay_and_wrong_tenant_cannot_change_subscriptions():
    from apps.integrations.email_preferences import address_hash
    from apps.integrations.mail_providers.webhooks import observe
    from apps.integrations.models_email import EmailLog, EmailProviderWebhookReceipt
    from apps.integrations.models_suppression import EmailSuppression
    from apps.makerspaces.models import Makerspace
    first = Makerspace.objects.create(name="First", slug="first-callback")
    second = Makerspace.objects.create(name="Second", slug="second-callback")
    log = EmailLog.objects.create(makerspace=first, to_email="to@example.org", subject="Test",
        status="sent", provider_name="resend", provider_message_id="opaque-id",
        provider_recipient_hash=address_hash(first.pk, "to@example.org"))
    event = MailEvent("event-id", "opaque-id", "complaint")
    assert observe(second, "resend", event) is False
    assert not EmailSuppression.objects.exists()
    assert observe(first, "resend", event) is True
    assert observe(first, "resend", event) is True
    assert EmailProviderWebhookReceipt.objects.count() == 1
    assert EmailSuppression.objects.get().makerspace_id == first.pk
    assert observe(first, "resend", MailEvent("late-delivery", "opaque-id", "delivered")) is True
    log.refresh_from_db()
    assert log.provider_delivery_status == "complaint"
    assert log.status == "sent"  # Provider observation cannot rewrite outbox acceptance.


@pytest.mark.django_db
def test_native_callback_view_is_disabled_by_default(settings):
    from rest_framework.test import APIRequestFactory
    from apps.integrations.views_bounce import ProviderBounceWebhookView
    settings.EMAIL_PROVIDER_WEBHOOKS_ENABLED = False
    request = APIRequestFactory().post("/callback", {}, format="json")
    response = ProviderBounceWebhookView.as_view()(request, makerspace_id=1, provider="resend")
    assert response.status_code == 404
