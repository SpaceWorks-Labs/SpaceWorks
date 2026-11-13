"""Signed provider events keep their original optional time across journal replay."""
import hashlib
import hmac
import json
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.integrations.models_cutover import NotificationIngress
from apps.integrations.models_endpoints import ChannelConfiguration
from apps.integrations.notification_api_serializers import ChannelSerializer
from apps.integrations.notification_ingress import process
from apps.integrations.notification_provider_references import remember
from apps.integrations.notification_sender import configuration_sender_key
from apps.integrations.notification_wa_meta_reference import client_reference
from apps.integrations.messaging.protections import recipient_hash
from apps.integrations.messaging.senders import reserve_sender
from .reconciliation_helpers import account, delivery, sms_config, space
from .test_fm_callback_urls import post_url, signed_form
from .test_reconciliation_signed_webhooks import twilio_configuration

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("provider", ["sms", "twilio-wa", "meta"])
@pytest.mark.parametrize("has_time", [False, True])
def test_signed_status_replay_never_invents_provider_time(settings, receipt_only_cutover, provider, has_time):
    settings.MESSAGING_WEBHOOK_BASE_URL = "https://api.example.test"
    now = timezone.now()
    original = (now - timedelta(days=3)).replace(microsecond=0)
    values = {}
    if provider == "sms":
        config = sms_config(space())
        reserve_sender(sender_key=config.sender_key, channel="sms", owner="makerspace", makerspace=config.makerspace,
            webhook_secret="b" * 32)
    elif provider == "twilio-wa":
        config = twilio_configuration()
    else:
        config = ChannelConfiguration(makerspace=space(), channel="whatsapp", provider="meta", generation=2,
            integration_identity="345", sender_key="meta:234:345")
        values = {"app_id": "123", "business_account_id": "234", "phone_number_id": "345",
            "access_token": "access", "app_secret": "secret", "webhook_verify_token": "verify"}
        config.set_credentials(values)
        config.save()
    message_id = "wamid.fm-time" if provider == "meta" else "SM" + "1" * 32
    row = delivery(config.makerspace, account(), channel=config.channel, state="accepted", attempt_count=1,
        provider_id=message_id, sender_key=configuration_sender_key(config),
        integration_generation=config.generation, integration_identity=config.integration_identity,
        recipient_phone_hash=recipient_hash("phone", "+14155550123"))
    row.provider = config.provider
    row.save(update_fields=["provider"])
    remember(row)
    urls = ChannelSerializer(config).data["callback_urls"]
    if provider == "meta":
        status = {"id": message_id, "status": "delivered", "recipient_id": "14155550123",
            "biz_opaque_callback_data": client_reference(config, row)}
        if has_time:
            status["timestamp"] = str(int(original.timestamp()))
        payload = {"object": "whatsapp_business_account", "entry": [{"id": "234", "changes": [{"field": "messages",
            "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "345"}, "statuses": [status]}}]}]}
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
        request = APIRequestFactory().post(urlsplit(urls["webhook_url"]).path, raw,
            content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature)
    else:
        prefix = "whatsapp:" if provider == "twilio-wa" else ""
        params = {"AccountSid": "AC" + "a" * 32, "MessageSid": message_id, "MessageStatus": "delivered",
            "From": prefix + "+14155550100", "To": prefix + "+14155550123"}
        if has_time:
            params["Timestamp"] = str(int(original.timestamp()))
        url = urls["status_url"] if provider == "sms" else urls["status_url_template"].replace("{delivery_id}", str(row.pk))
        request = signed_form(url, params)
    assert post_url(request).status_code == 200
    receipt = NotificationIngress.objects.get()
    NotificationIngress.objects.filter(pk=receipt.pk).update(received_at=original + timedelta(hours=1))
    receipt_only_cutover.route = "canonical"
    receipt_only_cutover.save(update_fields=["route"])
    assert process(receipt.pk)
    row.refresh_from_db()
    assert row.state == "delivered" and row.delivered_at == (original if has_time else None)
    assert row.updated_at >= now
