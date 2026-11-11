from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.urls import resolve, reverse
from django.utils import timezone

from apps.integrations.notification_providers import PROVIDERS, ProviderResult
from apps.integrations.notification_resolution import whatsapp_template
from apps.integrations.notification_wa_meta import MetaWhatsAppProvider
from apps.integrations.notification_wa_twilio import TwilioWhatsAppProvider
from apps.integrations.notification_wa_window import in_session_window


def test_meta_is_registered_mounted_and_tenant_bound():
    from apps.integrations.notification_wa_meta_views import MetaWebhookView
    from apps.makerspaces.origin_scope_routes import MAKERSPACE_KWARG_ROUTES
    from apps.tenant_migration.gate_policy_http import HTTP_ANONYMOUS_PARTICIPANTS, HTTP_ANONYMOUS_EXEMPTIONS
    assert PROVIDERS[("whatsapp", "meta")] is MetaWhatsAppProvider
    url = reverse("whatsapp-meta-webhook", kwargs={"makerspace_id": 12, "generation": 3, "phone_number_id": "123"})
    match = resolve(url)
    assert match.func.cls is MetaWebhookView and match.kwargs["makerspace_id"] == 12
    key = "apps.integrations.notification_wa_meta_views.MetaWebhookView.post"
    assert key in HTTP_ANONYMOUS_PARTICIPANTS and key not in HTTP_ANONYMOUS_EXEMPTIONS
    assert MAKERSPACE_KWARG_ROUTES["whatsapp-meta-webhook"] == "makerspace_id"


@pytest.mark.parametrize("age,expected", [(None, False), (0, True), (1, True), (86399, True), (86400, False), (86401, False), (-1, False)])
def test_shared_window_and_twilio_choose_the_same_boundary(age, expected, monkeypatch):
    now = timezone.now()
    endpoint = SimpleNamespace(last_inbound_at=now - timedelta(seconds=age) if age is not None else None,
        user_id=7, destination="+12025550123")
    assert in_session_window(endpoint, now=now) is expected
    monkeypatch.setattr("apps.integrations.notification_wa_window.timezone.now", lambda: now)
    config = SimpleNamespace(pk=1, makerspace_id=2, generation=3, integration_identity="wa")
    provider = TwilioWhatsAppProvider(config)
    monkeypatch.setattr(provider, "active", lambda: True)
    monkeypatch.setattr(provider, "valid_endpoint", lambda _: True)
    sent = Mock(return_value=ProviderResult(True, "provider-message"))
    monkeypatch.setattr(provider, "_send", sent)
    template = Mock(return_value={"ContentSid": "HX123"})
    monkeypatch.setattr("apps.integrations.notification_wa_twilio.template_payload", template)
    envelope = SimpleNamespace(makerspace_id=2, recipient_id=7, event="confirmed", audience="member", context={})
    delivery = SimpleNamespace(pk=4, endpoint=endpoint, envelope=envelope, makerspace_id=2,
        channel="whatsapp", provider="twilio", integration_generation=3, integration_identity="wa")
    assert provider.send(delivery, {"text": "Update"}).accepted
    assert (sent.call_args.args[1] == {"Body": "Update"}) is expected
    assert bool(template.call_count) is not expected


@pytest.mark.django_db
@pytest.mark.parametrize("age,uses_template", [(0, False), (86399, False), (86400, True), (-1, True)])
def test_dispatcher_window_does_not_bypass_template_with_future_time(world, age, uses_template):
    from apps.integrations.models_endpoints import WhatsAppTemplate
    config = world.config("whatsapp", provider="twilio")
    binding = WhatsAppTemplate.objects.create(configuration=config, event="confirmed", audience="member",
        locale="en", template_name="approved", approved=True)
    now = timezone.now()
    endpoint = SimpleNamespace(configuration=config, last_inbound_at=now - timedelta(seconds=age))
    delivery = SimpleNamespace(endpoint=endpoint, envelope=SimpleNamespace(event="confirmed", audience="member", context={}))
    assert whatsapp_template(delivery, now=now) == (binding if uses_template else None)


@pytest.mark.django_db
def test_twilio_reserved_bindings_match_meta_contract(world, monkeypatch):
    config = world.config("whatsapp", provider="twilio")
    challenge, code = world.challenge(config)
    challenge.candidate_destination = "+12025550123"
    provider = TwilioWhatsAppProvider(config)
    monkeypatch.setattr(provider, "active", lambda: True)
    monkeypatch.setattr(provider, "valid_endpoint", lambda _: True)
    monkeypatch.setattr(provider, "_send", lambda *_: ProviderResult(True))
    template = Mock(side_effect=[{"ContentVariables": '{"1":"' + code + '"}'}, {}])
    monkeypatch.setattr("apps.integrations.notification_wa_twilio.template_payload", template)
    provider.start_challenge(challenge, code)
    provider.test(SimpleNamespace(destination="+12025550123"))
    assert template.call_args_list[0].args[1:4] == ("notification_opt_in", "member", "en")
    assert template.call_args_list[1].args[1:4] == ("notification_test", "member", "en")


@pytest.mark.django_db
def test_mounted_meta_webhook_enforces_handshake_signature_and_generation(world):
    import hashlib
    import hmac
    import json
    config = world.config("whatsapp", provider="meta")
    config.set_credentials({"app_id": "1", "app_secret": "secret", "business_account_id": "2",
        "phone_number_id": "3", "access_token": "access-token", "webhook_verify_token": "verify-token"})
    config.save(update_fields=["credentials"])
    url = reverse("whatsapp-meta-webhook", kwargs={"makerspace_id": world.space.pk, "generation": config.generation,
                                                "phone_number_id": "3"})
    api = world.client()
    response = api.get(url, {"hub.mode": "subscribe", "hub.verify_token": "verify-token", "hub.challenge": "hello"})
    assert response.status_code == 200 and response.content == b"hello"
    raw = json.dumps({"object": "whatsapp_business_account", "entry": []}).encode()
    assert api.post(url, raw, content_type="application/json").status_code == 403
    signature = "sha256=" + hmac.new(b"secret", raw, hashlib.sha256).hexdigest()
    assert api.post(url, raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature).status_code == 200
    config.generation += 1
    config.save(update_fields=["generation"])
    assert api.post(url, raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=signature).status_code == 404
