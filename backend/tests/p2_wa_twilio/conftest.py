import base64
import hashlib
import hmac
import io
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.test import APIClient

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint, WhatsAppTemplate
from apps.integrations.notification_sender import configuration_sender_key
from apps.integrations.notification_wa_twilio import TwilioWhatsAppProvider
from apps.integrations.notification_wa_twilio_config import callback_path
from tests.return_helpers import make_member, make_space

ACCOUNT = "AC" + "1" * 32
TOKEN = "2" * 32
SENDER = "+14155550100"
DESTINATION = "+14155550123"
MESSAGE = "SM" + "3" * 32
CONTENT = "HX" + "4" * 32
PUBLIC = "https://api.example.test"


def signature(path, params, token=TOKEN):
    pairs = sorted((key, value) for key, value in params.items())
    text = PUBLIC + path + "".join(key + value for key, value in pairs)
    return base64.b64encode(hmac.new(token.encode(), text.encode(), hashlib.sha1).digest()).decode()


class FakeResponse(io.BytesIO):
    status = 201


@pytest.fixture(autouse=True)
def http(monkeypatch):
    calls = []
    state = {"error": None, "approval": "approved", "account": ACCOUNT}

    def open_request(req, timeout):
        calls.append((req, parse_qs(req.data.decode()) if req.data else {}))
        if state["error"]:
            raise state["error"]
        if req.get_method() != "GET":
            data = {"sid": MESSAGE, "status": "queued"}
        elif req.full_url.endswith("/ApprovalRequests"):
            data = {"sid": CONTENT, "account_sid": state["account"], "whatsapp": {"status": state["approval"]}}
        else:
            data = {"sid": CONTENT, "account_sid": state["account"], "language": "en",
                "types": {"twilio/text": {"body": "Tool {{1}}"}}, "variables": {"1": "Drill"}}

        return FakeResponse(json.dumps(data).encode())

    monkeypatch.setattr("apps.integrations.notification_wa_twilio_http.request.build_opener",
                        lambda *args: SimpleNamespace(open=open_request))
    return SimpleNamespace(calls=calls, state=state)


@pytest.fixture
def wa(settings, http, monkeypatch, django_capture_on_commit_callbacks):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    # The delivery path re-checks the envelope's source (live authority); a test source must be registered.
    from apps.integrations.notification_sources import NotificationSource, SOURCES
    monkeypatch.setitem(SOURCES, "wa.test", NotificationSource(lambda envelope: True))
    settings.ALLOWED_HOSTS = ["testserver", "internal-proxy.example.test"]
    space = make_space("wa-twilio")
    user = make_member("wa-owner", space)
    # One account per person (U-A1): personal WhatsApp needs a COMMUNITY tie; make_member only gives the staff row.
    from tests.accounts.account_factories import make_membership
    make_membership(user, space)
    # WhatsApp is opt-in per feature (catalogue default OFF): these tests deliver hardware-request events.
    from apps.integrations.models import NotificationPreference
    NotificationPreference.objects.update_or_create(makerspace=space, feature="hardware_requests", channel="whatsapp",
                                                    defaults={"enabled": True})
    config = ChannelConfiguration.objects.create(makerspace=space, channel="whatsapp", provider="twilio",
        enabled=True, personal_enabled=True, integration_identity="wa-business-one")
    credentials = {"account_sid": ACCOUNT, "auth_token": TOKEN, "whatsapp_sender": SENDER, "public_base_url": PUBLIC}
    config.set_credentials(credentials)
    config.save()
    digest = salted_hmac("notification.endpoint.identity.v1",
        f"{config.pk}:{config.generation}:{DESTINATION}", algorithm="sha256").hexdigest()
    endpoint = NotificationEndpoint.objects.create(makerspace=space, user=user, configuration=config,
        channel="whatsapp", provider="twilio", destination=DESTINATION, provider_subject=DESTINATION,
        identity_digest=digest, integration_identity=config.integration_identity,
        integration_generation=config.generation, verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
    envelope = NotificationEnvelope.objects.create(makerspace=space, recipient=user, feature="hardware_requests",
        stream="hardware", event="accepted", audience="requester", context={"tool": "Drill", "locale": "en"},
        source_kind="wa.test", dedup_key="wa:test")
    delivery = NotificationDelivery.objects.create(makerspace=space, envelope=envelope, channel="whatsapp",
        endpoint=endpoint, target_key=f"endpoint:{endpoint.pk}", provider="twilio",
        sender_key=configuration_sender_key(config),
        integration_generation=config.generation, integration_identity=config.integration_identity)

    def template(event="accepted", variables=None, approved=True, audience="requester"):
        return WhatsAppTemplate.objects.create(configuration=config, event=event, audience=audience,
            template_name=CONTENT, variables=["tool"] if variables is None else variables, approved=approved)

    def post(kind="inbound", params=None, *, path=None, signed=True,
             content_type="application/x-www-form-urlencoded"):
        path = path or callback_path(config, kind, delivery.pk if kind == "status" else None)
        data = {"AccountSid": ACCOUNT, "MessageSid": MESSAGE,
                "From": "whatsapp:" + (SENDER if kind == "status" else DESTINATION),
                "To": "whatsapp:" + (DESTINATION if kind == "status" else SENDER)}
        data.update(params or {})
        with django_capture_on_commit_callbacks(execute=True):
            return APIClient().post(path, urlencode(data), content_type=content_type,
                HTTP_X_TWILIO_SIGNATURE=signature(path, data) if signed else "invalid",
                HTTP_HOST="internal-proxy.example.test")

    return SimpleNamespace(space=space, user=user, config=config, credentials=credentials, endpoint=endpoint,
        envelope=envelope, delivery=delivery, provider=TwilioWhatsAppProvider(config), template=template, post=post,
        http=http)
