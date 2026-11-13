"""Signed compatibility webhooks feed the durable canonical journal (D1).

The original Twilio/Meta URLs stay on the durable adapter: they authenticate with
the sender's current or recently retired secret, commit STOP protection together
with an encrypted ``NotificationIngress`` receipt, and replay statuses only into
exactly matching canonical deliveries.
"""
import base64
import hashlib
import hmac
import json
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import urlencode
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from django.http import QueryDict
from django.urls import reverse
from django.utils import timezone

from apps.integrations.messaging.protections import recipient_hash
from apps.integrations.messaging.webhook_signatures import twilio_signature
from apps.integrations.models import MessagingSenderCredential, MessagingSuppression
from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.models_cutover import NotificationIngress
from apps.integrations.notification_ingress import process
from tests.messaging.canonical_helpers import (
    PLATFORM_FROM, PLATFORM_SMS_KEY, PLATFORM_WA_KEY, SID, envelope, platform_sms, platform_whatsapp,
)

pytestmark = pytest.mark.django_db
BASE = "https://callbacks.example.test"
INGRESS_WRITE = "apps.integrations.notification_ingress.NotificationIngress.objects.get_or_create"


@pytest.fixture
def pipeline(space, member):
    platform_sms()
    platform_whatsapp()
    return SimpleNamespace(space=space, member=member, wa=SimpleNamespace(sender_key=PLATFORM_WA_KEY),
        sms=SimpleNamespace(account_sid=SID, from_number=PLATFORM_FROM, sender_key=PLATFORM_SMS_KEY))


def leg(pipeline, *, channel="sms", provider_id="SMtest", key="leg"):
    """A canonical addressed delivery the provider already accepted."""
    intent = envelope(pipeline.space, pipeline.member, key=key, source_kind="migration.history")
    return NotificationDelivery.objects.create(makerspace=pipeline.space, envelope=intent, channel=channel,
        target_key=channel, provider="twilio" if channel == "sms" else "meta", state="accepted",
        sender_key=pipeline.sms.sender_key if channel == "sms" else pipeline.wa.sender_key, provider_id=provider_id,
        recipient_phone_hash=recipient_hash("phone", pipeline.member.phone_e164))


def twilio_post(client, pipeline, *, kind="status", secret="twilio-secret", fields=None, signed_url=None, extra=""):
    path = reverse("messaging-twilio-platform-" + kind)
    fields = fields or {"AccountSid": pipeline.sms.account_sid, "From": pipeline.sms.from_number,
        "To": pipeline.member.phone_e164, "MessageSid": "SMtest", "MessageStatus": "delivered", "NumSegments": "2"}
    body = urlencode(fields, doseq=True)
    signature = twilio_signature(secret, signed_url or BASE + path, QueryDict(body))
    return client.post(path, body + extra, content_type="application/x-www-form-urlencoded", HTTP_X_TWILIO_SIGNATURE=signature)


def meta_post(client, document, *, secret="meta-secret"):
    raw = json.dumps(document).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return client.post(reverse("messaging-meta-platform"), raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature)


def meta_document(*, phone="123", business="456", statuses=None, messages=None, contacts=None):
    return {"entry": [{"id": business, "changes": [{"field": "messages", "value": {"metadata": {"phone_number_id": phone},
        "statuses": statuses or [], "messages": messages or [], "contacts": contacts or []}}]}]}


def test_twilio_published_signature_vector():
    params = {"CallSid": "CA1234567890ABCDE", "Caller": "+14158675309", "Digits": "1234",
              "From": "+14158675309", "To": "+18005551212"}
    assert twilio_signature("12345", "https://mycompany.com/myapp.php?foo=1&bar=2", params) == "RSOYDt4T1cUTdK1PDd93/VVr8B8="


def test_twilio_official_repeated_parameter_vector():
    params = QueryDict("Sid=CA123&SidAccount=AC123&Digits=5678&Digits=1234&Digits=1234")
    assert twilio_signature("12345", "https://mycompany.com/myapp.php?foo=1&bar=2", params) == "IK+Dwps556ElfBT0I3Rgjkr1wJU="


def test_valid_twilio_status_early_callback_duplicate_and_billed_segments(pipeline, client):
    assert twilio_post(client, pipeline).status_code == 200
    receipt = NotificationIngress.objects.get()
    assert receipt.state == "held"  # Early: no delivery to correlate yet; kept for replay.
    row = leg(pipeline)
    assert process(receipt.pk)
    assert twilio_post(client, pipeline).status_code == 200
    assert NotificationIngress.objects.count() == 1
    row.refresh_from_db()
    assert (row.state, row.billed_segments) == ("delivered", 2)
    assert row.delivered_at is None  # Twilio did not supply a timestamp.


@pytest.mark.parametrize("defect", ["wrong_url", "extra_field", "account", "number", "repeated_identity"])
def test_twilio_rejects_wrong_url_fields_and_bindings(pipeline, client, defect):
    fields = {"AccountSid": pipeline.sms.account_sid, "From": pipeline.sms.from_number,
              "MessageSid": "SMbad", "MessageStatus": "sent"}
    kwargs = {"fields": fields}
    if defect == "wrong_url":
        kwargs["signed_url"] = "https://wrong.example.test" + reverse("messaging-twilio-platform-status")
    elif defect == "extra_field":
        kwargs["extra"] = "&Extra=unsigned"
    elif defect == "account":
        fields["AccountSid"] = "ACforeign"
    elif defect == "number":
        fields["From"] = "+14155559999"
    else:
        fields["AccountSid"] = [pipeline.sms.account_sid, "ACforeign"]
    assert twilio_post(client, pipeline, **kwargs).status_code == 403
    assert not NotificationIngress.objects.exists()


def test_twilio_repeated_values_port_variants_and_json_refusal(pipeline, client):
    fields = {"AccountSid": pipeline.sms.account_sid, "From": pipeline.sms.from_number,
              "MessageSid": "SMrepeat", "MessageStatus": "sent", "Extra": ["z", "a", "z"]}
    path = reverse("messaging-twilio-platform-status")
    assert twilio_post(client, pipeline, fields=fields, signed_url="https://callbacks.example.test:443" + path).status_code == 200
    assert client.post(path, fields, format="json").status_code == 415


# A STOP keyword body is always honoured: provider OptOutType can add, never
# downgrade, sender-level protection. START never grants or lifts anything.
@pytest.mark.parametrize("keyword,opt_out,expected", [("hi", "STOP", True), ("STOP", "HELP", True),
    ("REVOKE", "", True), ("OPTOUT", "", True), ("START", "START", False), ("hi", "HELP", False)])
def test_optout_precedence_keywords_and_twiml(pipeline, client, keyword, opt_out, expected):
    fields = {"AccountSid": pipeline.sms.account_sid, "To": pipeline.sms.from_number,
        "From": pipeline.member.phone_e164, "MessageSid": "SMstop", "Body": keyword, "OptOutType": opt_out}
    response = twilio_post(client, pipeline, kind="inbound", fields=fields)
    assert response.status_code == 200 and response["Content-Type"].startswith("text/xml")
    assert b"<Response/>" in response.content
    assert MessagingSuppression.objects.exists() == expected
    receipt = NotificationIngress.objects.get()
    assert receipt.protection_applied and "Body" not in receipt.get_payload()
    assert receipt.payload.startswith("fernet:")  # Encrypted at rest; the body is never journaled.


def test_start_never_lifts_application_suppression(pipeline, client):
    fields = {"AccountSid": pipeline.sms.account_sid, "To": pipeline.sms.from_number,
        "From": pipeline.member.phone_e164, "MessageSid": "SMstop", "Body": "STOP"}
    twilio_post(client, pipeline, kind="inbound", fields=fields)
    fields.update(MessageSid="SMstart", Body="START", OptOutType="START")
    twilio_post(client, pipeline, kind="inbound", fields=fields)
    assert MessagingSuppression.objects.filter(lifted_at__isnull=True).count() == 1


def test_webhook_database_failure_returns_500(pipeline, client):
    with patch(INGRESS_WRITE, side_effect=DatabaseError):
        assert twilio_post(client, pipeline).status_code == 500


def test_meta_challenge_signature_and_foreign_phone_id(pipeline, client):
    from apps.integrations.models import PlatformWhatsAppSettings
    path = reverse("messaging-meta-platform")
    token = PlatformWhatsAppSettings.objects.get().webhook_verify_token
    response = client.get(path, {"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "challenge-123"})
    assert response.status_code == 200 and response.content == b"challenge-123"
    assert client.get(path, {"hub.mode": "subscribe", "hub.verify_token": "bad"}).status_code == 403
    for doc in (meta_document(phone="foreign", statuses=[{"id": "wamid.foreign", "status": "sent"}]),
                meta_document(business="999", statuses=[{"id": "wamid.foreign-waba", "status": "sent"}])):
        assert meta_post(client, doc).status_code == 200
    assert not NotificationIngress.objects.exists()
    assert meta_post(client, doc, secret="bad").status_code == 403


def test_meta_db_failure_returns_500(pipeline, client):
    doc = meta_document(statuses=[{"id": "wamid.db", "status": "sent"}])
    with patch(INGRESS_WRITE, side_effect=DatabaseError):
        assert meta_post(client, doc).status_code == 500


def test_retired_credentials_window_and_wipe(pipeline, client):
    from apps.integrations.messaging.senders import reserve_sender, wipe_retired_credentials
    identity = MessagingSenderCredential.objects.get(identity__sender_key=pipeline.sms.sender_key).identity
    reserve_sender(sender_key=identity.sender_key, channel="sms", owner="platform", webhook_secret="new-secret")
    assert twilio_post(client, pipeline).status_code == 200
    old = identity.credentials.get(version=1)
    MessagingSenderCredential.objects.filter(pk=old.pk).update(retired_at=timezone.now() - timedelta(days=15))
    assert twilio_post(client, pipeline).status_code == 403
    # A retired verifier is never wiped while a receipt it authenticated awaits replay.
    assert NotificationIngress.objects.get().state == "held"
    assert wipe_retired_credentials() == 0
    NotificationIngress.objects.update(state="processed", processed_at=timezone.now())
    assert wipe_retired_credentials() == 1
    old.refresh_from_db()
    assert old.webhook_secret == "" and old.wiped_at is not None


def test_twilio_query_string_is_signed_verbatim(pipeline, client):
    path = reverse("messaging-twilio-platform-status") + "?tag=z%2Fa&tag=a"
    body = urlencode({"AccountSid": pipeline.sms.account_sid, "From": pipeline.sms.from_number,
                      "MessageSid": "SMquery", "MessageStatus": "sent"})
    signature = twilio_signature("twilio-secret", BASE + path, QueryDict(body))
    assert client.post(path, body, content_type="application/x-www-form-urlencoded",
                       HTTP_X_TWILIO_SIGNATURE=signature).status_code == 200
    assert client.post(path.replace("z%2Fa", "z/a"), body, content_type="application/x-www-form-urlencoded",
                       HTTP_X_TWILIO_SIGNATURE=signature).status_code == 403


def test_protection_failure_is_not_acknowledged_and_provider_retry_succeeds(pipeline, client):
    fields = {"AccountSid": pipeline.sms.account_sid, "To": pipeline.sms.from_number,
        "From": pipeline.member.phone_e164, "MessageSid": "SMdurable", "Body": "STOP"}
    with patch("apps.integrations.messaging.stops.process_stop", side_effect=DatabaseError):
        assert twilio_post(client, pipeline, kind="inbound", fields=fields).status_code == 500
    # STOP protection and its receipt commit together; a failure acknowledges neither.
    assert not NotificationIngress.objects.exists() and not MessagingSuppression.objects.exists()
    assert twilio_post(client, pipeline, kind="inbound", fields=fields).status_code == 200
    receipt = NotificationIngress.objects.get()
    assert receipt.state == "processed" and receipt.protection_applied
    assert MessagingSuppression.objects.exists()


def test_retired_meta_secret_verification_window(pipeline, client):
    from apps.integrations.messaging.senders import reserve_sender
    identity = MessagingSenderCredential.objects.get(identity__sender_key=pipeline.wa.sender_key).identity
    reserve_sender(sender_key=identity.sender_key, channel="whatsapp", owner="platform", webhook_secret="new-meta-secret")
    doc = meta_document(statuses=[{"id": "wamid.old-secret", "status": "sent"}])
    assert meta_post(client, doc).status_code == 200
    MessagingSenderCredential.objects.filter(identity=identity, version=1).update(retired_at=timezone.now() - timedelta(days=15))
    assert meta_post(client, doc).status_code == 403
    assert meta_post(client, doc, secret="new-meta-secret").status_code == 200


def test_meta_contacts_context_alias_stop_and_no_plaintext_payload(pipeline, client):
    from apps.integrations.messaging.protections import suppressed
    leg(pipeline, channel="whatsapp", provider_id="wamid.context")
    doc = meta_document(messages=[{"id": "wamid.stop-context", "from_user_id": "business-user",
        "context": {"id": "wamid.context"}, "text": {"body": "STOP"}}])
    assert meta_post(client, doc).status_code == 200
    phone = recipient_hash("phone", pipeline.member.phone_e164)
    assert suppressed("whatsapp", pipeline.wa.sender_key, phone)
    assert suppressed("whatsapp", pipeline.wa.sender_key, recipient_hash("alias", "business-user"))
    receipt = NotificationIngress.objects.get(channel="whatsapp")
    payload = receipt.get_payload()
    assert "STOP" not in str(payload) and pipeline.member.phone_e164 not in str(payload)
    assert receipt.payload.startswith("fernet:")


def test_active_identity_precedes_higher_version_retired_identity(pipeline):
    from apps.integrations.messaging.senders import callback_credentials, reserve_sender, retire_sender
    old_key = pipeline.sms.sender_key
    for secret in ("version-two", "version-three"):
        old = reserve_sender(sender_key=old_key, channel="sms", owner="platform", webhook_secret=secret)
    retire_sender(old)
    active = reserve_sender(sender_key="twilio:ACdifferent:+14155550004", channel="sms", owner="platform", webhook_secret="active")
    assert callback_credentials(channel="sms", owner="platform").first().identity_id == active.pk
