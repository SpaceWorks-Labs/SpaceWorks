"""Decision #86c: the generic bounce webhook's record is canonical, and the native
provider callback forwards every bounce/complaint into it."""

import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from django.urls import reverse
from rest_framework.test import APIClient, APIRequestFactory

from apps.audit.models import AuditLog
from apps.integrations.email_preferences import address_hash
from apps.integrations.models_email import EmailLog, EmailProviderWebhookReceipt
from apps.integrations.models_suppression import EmailSuppression
from apps.integrations.models_timing import NotificationTimingPolicy
from apps.integrations.models_tracking import EmailProviderEvent
from apps.integrations.views_bounce import ProviderBounceWebhookView
from tests.return_helpers import make_space

pytestmark = pytest.mark.django_db
SECRET = "test-inbound-signing-secret-0123456789"
KEY = b"0123456789abcdef0123456789abcdef"


def sent_log(space, message_id="opaque-id", address="member@example.test"):
    return EmailLog.objects.create(makerspace=space, to_email=address, subject="Notice", status="sent",
        provider_name="resend", provider_message_id=message_id,
        provider_recipient_hash=address_hash(space.pk, address))


def generic(space, *, event_id="evt-1", reason="bounce", message_id="opaque-id"):
    policy = NotificationTimingPolicy.objects.filter(makerspace=space).first() or NotificationTimingPolicy(makerspace=space)
    policy.set_bounce_secret(SECRET)
    policy.save()
    stamp = str(int(time.time()))
    raw = json.dumps({"event_id": event_id, "message_id": message_id, "address": "Member@Example.test", "reason": reason})
    signature = hmac.new(SECRET.encode(), stamp.encode() + b"." + raw.encode(), hashlib.sha256).hexdigest()
    return APIClient().post(reverse("email-bounce-webhook", kwargs={"makerspace_id": space.pk}), raw,
        content_type="application/json", HTTP_X_SPACEWORKS_TIMESTAMP=stamp, HTTP_X_SPACEWORKS_SIGNATURE=signature)


def native(space, monkeypatch, settings, *, event_type="email.bounced", event_id="svix-event"):
    settings.EMAIL_PROVIDER_WEBHOOKS_ENABLED = True
    from apps.integrations.mail_providers import selection
    config = SimpleNamespace(provider="resend", credentials={"webhook_secret": "whsec_" + base64.b64encode(KEY).decode()})
    monkeypatch.setattr(selection, "stored_config", lambda makerspace, tenant: config)
    raw = json.dumps({"type": event_type, "data": {"email_id": "opaque-id"}}).encode()
    stamp = str(int(time.time()))
    signature = base64.b64encode(hmac.new(KEY, event_id.encode() + b"." + stamp.encode() + b"." + raw,
                                          hashlib.sha256).digest()).decode()
    request = APIRequestFactory().post("/callback", raw, content_type="application/json",
        HTTP_SVIX_ID=event_id, HTTP_SVIX_TIMESTAMP=stamp, HTTP_SVIX_SIGNATURE="v1," + signature)
    return ProviderBounceWebhookView.as_view()(request, makerspace_id=space.pk, provider="resend")


def canonical_state(space):
    log = EmailLog.objects.get(makerspace=space)
    return {
        "events": EmailProviderEvent.objects.filter(makerspace=space).count(),
        "bounced": log.bounced_at is not None, "complained": log.complained_at is not None,
        "suppression": list(EmailSuppression.objects.filter(makerspace=space).values_list("reason", flat=True)),
        "received": AuditLog.objects.filter(action="email.provider_event_received").count(),
        "suppressed": AuditLog.objects.filter(action="email.suppressed_provider").count(),
    }


def test_generic_route_writes_the_canonical_record_once():
    space = make_space("d86-generic")
    sent_log(space)
    assert generic(space).status_code == 200 and generic(space).status_code == 200
    assert canonical_state(space) == {"events": 1, "bounced": True, "complained": False,
                                      "suppression": ["bounce"], "received": 1, "suppressed": 1}


def test_native_route_forwards_into_the_same_canonical_record(monkeypatch, settings):
    space = make_space("d86-native")
    log = sent_log(space)
    assert native(space, monkeypatch, settings).status_code == 200
    assert native(space, monkeypatch, settings).status_code == 200  # replay
    assert canonical_state(space) == {"events": 1, "bounced": True, "complained": False,
                                      "suppression": ["bounce"], "received": 1, "suppressed": 1}
    event = EmailProviderEvent.objects.get(makerspace=space)
    assert event.reason == "bounce" and event.event_id.startswith("resend:")
    assert EmailProviderWebhookReceipt.objects.filter(log=log).count() == 1
    log.refresh_from_db()
    assert log.provider_delivery_status == "bounce"


def test_native_complaint_upgrades_a_generic_bounce_without_a_second_suppression(monkeypatch, settings):
    space = make_space("d86-both")
    sent_log(space)
    assert generic(space).status_code == 200
    assert native(space, monkeypatch, settings, event_type="email.complained").status_code == 200
    state = canonical_state(space)
    assert state["events"] == 2 and state["bounced"] and state["complained"]
    assert state["suppression"] == ["complaint"] and state["suppressed"] == 2


def test_native_delivery_observation_records_no_bounce(monkeypatch, settings):
    space = make_space("d86-delivered")
    log = sent_log(space)
    assert native(space, monkeypatch, settings, event_type="email.delivered").status_code == 200
    log.refresh_from_db()
    assert log.provider_delivery_status == "delivered"
    assert not EmailProviderEvent.objects.exists() and not EmailSuppression.objects.exists()
