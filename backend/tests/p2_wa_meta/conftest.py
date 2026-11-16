"""Meta lane tests never contact a provider or use real credentials."""
import hashlib
import hmac
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.test import APIRequestFactory

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge
from apps.integrations.notification_proofs import digest
from apps.integrations.notification_providers import PROVIDERS
from apps.integrations.notification_wa_meta import MetaWhatsAppProvider
from apps.integrations.notification_wa_meta_views import MetaWebhookView
from tests.return_helpers import make_space, make_user


@pytest.fixture(autouse=True)
def no_provider_network(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("A Meta test attempted unmocked HTTP")
    monkeypatch.setattr("requests.request", refused)


@pytest.fixture
def wa(settings, monkeypatch, django_capture_on_commit_callbacks):
    settings.API_CLIENT_ENC_KEY = Fernet.generate_key().decode()
    # The delivery path re-checks the envelope's source (live authority); a test source must be registered.
    from apps.integrations.notification_sources import NotificationSource, SOURCES
    monkeypatch.setitem(SOURCES, "meta.test", NotificationSource(lambda envelope: True))
    space = make_space("wa-meta-test")
    space.enabled_modules = sorted(set(space.enabled_modules or []) | {"notifications"})
    space.save(update_fields=["enabled_modules"])
    user = make_user("meta-user")
    from tests.accounts.account_factories import make_membership
    make_membership(user, space)  # personal WhatsApp needs a community tie
    # WhatsApp is opt-in per feature (catalogue default OFF): these tests deliver hardware-request events.
    from apps.integrations.models import NotificationPreference
    NotificationPreference.objects.update_or_create(makerspace=space, feature="hardware_requests", channel="whatsapp",
                                                    defaults={"enabled": True})
    config = ChannelConfiguration.objects.create(makerspace=space, channel="whatsapp", provider="meta",
        enabled=True, personal_enabled=True, integration_identity="meta-install-1")
    secrets = {"app_id": "100", "app_secret": "test-app-secret", "business_account_id": "200",
               "phone_number_id": "300", "access_token": "test-permanent-token", "webhook_verify_token": "verify-me"}
    config.set_credentials(secrets)
    config.save(update_fields=["credentials"])
    monkeypatch.setitem(PROVIDERS, ("whatsapp", "meta"), MetaWhatsAppProvider)

    def endpoint(number="+15551234567", **overrides):
        identity_digest = salted_hmac("notification.endpoint.identity.v1",
            f"{config.pk}:{config.generation}:{number}", algorithm="sha256").hexdigest()
        values = dict(makerspace=space, user=user, configuration=config, channel="whatsapp", provider="meta",
            destination=number, provider_subject=number, identity_digest=identity_digest,
            integration_identity=config.integration_identity, integration_generation=config.generation,
            verified_at=timezone.now() - timedelta(hours=1), consented_at=timezone.now() - timedelta(hours=1), consent_version="v1")
        values.update(overrides)
        return NotificationEndpoint.objects.create(**values)

    def challenge(candidate="+15551234567", **overrides):
        code = "A" * 43
        values = dict(makerspace=space, user=user, configuration=config, integration_generation=config.generation,
            integration_identity=config.integration_identity, code_digest=digest(code),
            expires_at=timezone.now() + timedelta(minutes=10), consented_at=timezone.now(), consent_version="v1",
            candidate_destination=candidate)
        values.update(overrides)
        return NotificationEndpointChallenge.objects.create(**values), code

    def delivery(target, **overrides):
        envelope = NotificationEnvelope.objects.create(makerspace=space, recipient=user, feature="hardware_requests",
            event="accepted", audience="requester", source_kind="meta.test", dedup_key="wa-meta:accepted",
            context={"locale": "en", "reference": "LOAN-123"})
        from apps.integrations.notification_sender import configuration_sender_key
        values = dict(makerspace=space, envelope=envelope, endpoint=target, channel="whatsapp", provider="meta",
            sender_key=configuration_sender_key(config),
            integration_generation=config.generation, integration_identity=config.integration_identity,
            target_key=f"endpoint:{target.pk}", state="accepted", provider_id="wamid.test")
        values.update(overrides)
        return NotificationDelivery.objects.create(**values)

    def payload(kind, rows, *, phone="300", business="200", field="messages"):
        return {"object": "whatsapp_business_account", "entry": [{"id": business, "changes": [{
            "field": field, "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": phone}, kind: rows}}]}]}

    def post(data, *, signature=None, generation=None, phone="300", tenant=None, raw=None):
        raw = raw if raw is not None else json.dumps(data, separators=(",", ":")).encode()
        signature = signature or "sha256=" + hmac.new(secrets["app_secret"].encode(), raw, hashlib.sha256).hexdigest()
        request = APIRequestFactory().post("/meta/webhook", data=raw, content_type="application/json",
                                          HTTP_X_HUB_SIGNATURE_256=signature)
        # A STOP annotates the consent ledger in an on_commit hook: run it as production would.
        with django_capture_on_commit_callbacks(execute=True):
            return MetaWebhookView.as_view()(request, makerspace_id=tenant or space.pk,
                generation=generation or config.generation, phone_number_id=phone)

    def message(text="Hello", *, timestamp=None, sender="15551234567", message_id="wamid.inbound"):
        return {"id": message_id, "from": sender, "timestamp": str(timestamp or int(timezone.now().timestamp())),
                "type": "text", "text": {"body": text}}

    return SimpleNamespace(space=space, user=user, config=config, secrets=secrets,
        endpoint=endpoint, challenge=challenge, delivery=delivery, payload=payload, post=post,
        message=message, provider=MetaWhatsAppProvider(config))
