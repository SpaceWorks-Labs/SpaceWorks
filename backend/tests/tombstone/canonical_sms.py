"""Canonical addressed-SMS helpers for the tombstone profile (not collected as tests)."""
from unittest.mock import patch


def canonical_sms_leg(space, user, *, key, monkeypatch):
    """A bound canonical SMS intent from a registered source, exactly as adapters emit."""
    from apps.integrations.messaging.protections import recipient_hash
    from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
    from apps.integrations.notification_addressed import snapshot
    from apps.integrations.notification_sources import SOURCES, NotificationSource
    from tests.messaging.canonical_helpers import PLATFORM_SMS_KEY, envelope

    monkeypatch.setitem(SOURCES, "messaging.tombstone", NotificationSource(lambda _: True))
    intent = envelope(space, user, key=key, source_kind="messaging.tombstone")
    NotificationEnvelope.objects.filter(pk=intent.pk).update(
        context={"makerspace.name": space.name}, routing_snapshot={"sms": snapshot(intent)})
    intent.refresh_from_db()
    assert intent.routing_snapshot["sms"], "consent/sender binding must exist before sending"
    return NotificationDelivery.objects.create(makerspace=space, envelope=intent, channel="sms",
        target_key="sms", provider="twilio", sender_key=PLATFORM_SMS_KEY, provider_source="platform",
        recipient_phone_hash=recipient_hash("phone", user.phone_e164))


def send_accepted(leg, message_id):
    from apps.integrations.messaging.transport import SendResult
    from apps.integrations.notification_delivery import send
    with patch("apps.integrations.messaging.twilio.send_message",
               return_value=SendResult(message_id=message_id)) as provider:
        send(leg.pk)
    provider.assert_called_once()
    leg.refresh_from_db()
    return leg
