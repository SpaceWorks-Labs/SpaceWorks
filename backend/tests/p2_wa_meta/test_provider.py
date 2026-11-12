from datetime import timedelta
from types import SimpleNamespace

import pytest
import requests
from django.utils import timezone

from apps.integrations.models_endpoints import WhatsAppTemplate
from apps.integrations.notification_wa_meta import MetaWhatsAppProvider, register_meta_provider
from apps.integrations.notification_wa_meta_http import credentials
from apps.integrations.notification_wa_meta_templates import sync_templates
from apps.integrations.notification_wa_window import in_session_window

pytestmark = pytest.mark.django_db


def http(monkeypatch, *, code=200, payload=None, retry_after=""):
    calls = []
    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        body = payload if payload is not None else {"messages": [{"id": "wamid.accepted"}]}
        if method == "GET" and payload is None:
            body = {"data": [{"name": "loan_approved", "language": "en", "status": "APPROVED"},
                {"name": "opt_in", "language": "en", "status": "APPROVED"},
                {"name": "diagnostic", "language": "en", "status": "APPROVED"}]}
        return SimpleNamespace(status_code=code, headers={"Retry-After": retry_after}, json=lambda: body)
    monkeypatch.setattr("requests.request", request)
    return calls


def test_provider_registration_is_idempotent(wa):
    from apps.integrations.notification_providers import provider_for
    register_meta_provider()
    register_meta_provider()
    assert isinstance(provider_for(wa.config), MetaWhatsAppProvider)


def test_credential_storage_is_encrypted(wa):
    assert wa.config.credentials.startswith("fernet:")
    assert wa.secrets["access_token"] not in wa.config.credentials
    assert credentials(wa.config) == wa.secrets


def test_readiness_follows_the_whatsapp_module(wa):
    from apps.makerspaces.module_registry import MODULE_KEYS

    # WhatsApp is its own module now (it was folded under notifications in release 1).
    assert "whatsapp" in MODULE_KEYS
    assert "whatsapp" in wa.space.enabled_modules
    assert wa.provider._ready()
    wa.config.makerspace.enabled_modules = [key for key in wa.space.enabled_modules if key != "whatsapp"]
    assert not wa.provider._ready()


def test_free_text_inside_window(wa, monkeypatch):
    calls = http(monkeypatch)
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(minutes=1))
    result = wa.provider.send(wa.delivery(endpoint), {"text": "Loan accepted"})
    assert result.accepted and result.provider_id == "wamid.accepted"
    assert len(calls) == 1
    method, url, args = calls[0]
    assert method == "POST" and url.endswith("/300/messages")
    assert args["json"]["text"]["body"] == "Loan accepted"
    assert args["json"]["to"] == "15551234567"
    assert args["headers"]["Authorization"] == "Bearer test-permanent-token"
    assert args["allow_redirects"] is False and args["timeout"] == (5, 15)


@pytest.mark.parametrize("hours", [24, 25])
def test_free_text_outside_window_requires_binding(wa, monkeypatch, hours):
    calls = http(monkeypatch)
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(hours=hours))
    result = wa.provider.send(wa.delivery(endpoint), {"text": "Private rendered body"})
    assert not result.accepted and result.error_code == "template_required"
    assert all(method == "GET" for method, _, _ in calls)


def test_approved_template_uses_only_bound_safe_context(wa, monkeypatch):
    calls = http(monkeypatch)
    binding = WhatsAppTemplate.objects.create(configuration=wa.config, event="accepted", audience="requester",
        template_name="loan_approved", locale="en", variables=["reference"], approved=True)
    endpoint = wa.endpoint()
    result = wa.provider.send(wa.delivery(endpoint), {"text": "Private rendered body",
        "whatsapp_template": {"name": "attacker_template", "variables": ["secret"]}})
    assert result.accepted
    content = calls[-1][2]["json"]
    assert content["type"] == "template" and content["template"]["name"] == binding.template_name
    assert content["template"]["language"] == {"code": "en"}
    assert content["template"]["components"] == [{"type": "body", "parameters": [{"type": "text", "text": "LOAN-123"}]}]
    assert "Private rendered body" not in str(content)


def test_missing_context_never_falls_back_to_private_body(wa, monkeypatch):
    calls = http(monkeypatch)
    WhatsAppTemplate.objects.create(configuration=wa.config, event="accepted", audience="requester",
        template_name="loan_approved", variables=["unknown"], approved=True)
    result = wa.provider.send(wa.delivery(wa.endpoint()), {"text": "Private"})
    assert result.error_code == "template_required"
    assert all(method == "GET" for method, _, _ in calls)


def test_unapproved_template_cannot_send(wa, monkeypatch):
    calls = http(monkeypatch, payload={"data": []})
    binding = WhatsAppTemplate.objects.create(configuration=wa.config, event="accepted", audience="requester",
        template_name="loan_approved", variables=[], approved=True)
    result = wa.provider.send(wa.delivery(wa.endpoint()), {"text": "Private"})
    binding.refresh_from_db()
    assert not binding.approved and result.error_code == "template_required"
    assert all(method == "GET" for method, _, _ in calls)


def test_consent_withdrawal_during_template_lookup_prevents_send(wa, monkeypatch):
    from apps.integrations.models_endpoints import NotificationEndpoint
    calls = http(monkeypatch)
    original = requests.request
    endpoint = wa.endpoint()
    WhatsAppTemplate.objects.create(configuration=wa.config, event="accepted", audience="requester",
        template_name="loan_approved", variables=[], approved=True)
    def request(method, url, **kwargs):
        if method == "GET":
            NotificationEndpoint.objects.filter(pk=endpoint.pk).update(revoked_at=timezone.now())
        return original(method, url, **kwargs)
    monkeypatch.setattr("requests.request", request)
    result = wa.provider.send(wa.delivery(endpoint), {"text": "Private"})
    assert result.error_code == "invalid_endpoint" and all(method == "GET" for method, _, _ in calls)


def test_generation_rotation_during_template_lookup_prevents_send(wa, monkeypatch):
    from apps.integrations.models_endpoints import ChannelConfiguration
    calls = http(monkeypatch)
    original = requests.request
    WhatsAppTemplate.objects.create(configuration=wa.config, event="accepted", audience="requester",
        template_name="loan_approved", variables=[], approved=True)
    def request(method, url, **kwargs):
        if method == "GET":
            ChannelConfiguration.objects.filter(pk=wa.config.pk).update(generation=wa.config.generation + 1)
        return original(method, url, **kwargs)
    monkeypatch.setattr("requests.request", request)
    result = wa.provider.send(wa.delivery(wa.endpoint()), {"text": "Private"})
    assert result.error_code == "not_configured" and all(method == "GET" for method, _, _ in calls)


def test_approval_refresh_cannot_follow_untrusted_next_url(wa, monkeypatch):
    calls = []
    def request(method, url, **kwargs):
        calls.append(url)
        body = {"data": [], "paging": {"next": "https://attacker.invalid/steal"}} if len(calls) == 1 else {"data": []}
        return SimpleNamespace(status_code=200, headers={}, json=lambda: body)
    monkeypatch.setattr("requests.request", request)
    assert sync_templates(wa.config).error_code == "provider_error"
    assert len(calls) == 1 and calls[0].startswith("https://graph.facebook.com/")


def test_challenge_sends_approved_opt_in_code_template(wa, monkeypatch):
    calls = http(monkeypatch)
    WhatsAppTemplate.objects.create(configuration=wa.config, event="notification_opt_in", audience="member",
        template_name="opt_in", variables=["code"], approved=True)
    challenge, code = wa.challenge()
    result = wa.provider.start_challenge(challenge, code)
    assert "instructions" in result
    template = calls[-1][2]["json"]["template"]
    assert template["name"] == "opt_in"
    assert template["components"][0]["parameters"] == [{"type": "text", "text": code}]


def test_challenge_without_binding_fails_closed(wa, monkeypatch):
    calls = http(monkeypatch)
    challenge, code = wa.challenge()
    with pytest.raises(ValueError, match="template_required"):
        wa.provider.start_challenge(challenge, code)
    assert all(method == "GET" for method, _, _ in calls)


def test_user_initiated_opt_in_has_no_network(wa):
    challenge, code = wa.challenge(candidate="")
    assert code in wa.provider.start_challenge(challenge, code)["instructions"]


def test_test_send_is_a_fixed_diagnostic_and_syncs_approval(wa, monkeypatch):
    calls = http(monkeypatch)
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(seconds=1))
    assert wa.provider.test(endpoint).accepted
    assert calls[-1][2]["json"]["text"]["body"] == "Space Works WhatsApp delivery test."
    assert calls[0][0] == "GET"


def test_test_rejects_staff_rooms(wa):
    assert wa.provider.test(SimpleNamespace(pk=100)).error_code == "invalid_endpoint"


@pytest.mark.parametrize("code,status,expected,retryable", [
    (131047, 400, "template_required", False), (131026, 400, "invalid_endpoint", False),
    (131030, 400, "invalid_endpoint", False), (131050, 400, "blocked", False),
    (130429, 400, "rate_limited", True), (131056, 400, "rate_limited", True),
    (None, 429, "rate_limited", True), (None, 503, "unavailable", True),
    (190, 401, "not_configured", False), (9999, 400, "provider_error", False),
])
def test_errors_are_fixed_codes_and_never_echo_provider_text(wa, monkeypatch, code, status, expected, retryable):
    http(monkeypatch, code=status, payload={"error": {"code": code, "message": "secret token and private destination"}})
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(minutes=1))
    result = wa.provider.send(wa.delivery(endpoint), {"text": "Private"})
    assert result.error_code == result.sanitized_error == expected and result.retryable == retryable
    assert "secret" not in str(result)


@pytest.mark.parametrize("exception,expected", [(requests.Timeout, "timeout"), (requests.ConnectionError, "unavailable")])
def test_ambiguous_network_failure_is_bounded_by_shared_retry_policy(wa, monkeypatch, exception, expected):
    def failed(*args, **kwargs):
        raise exception("do not log this private request")
    monkeypatch.setattr("requests.request", failed)
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(minutes=1))
    result = wa.provider.send(wa.delivery(endpoint), {"text": "Private"})
    assert result.retryable and result.ambiguous and result.error_code == expected


def test_retry_after_is_bounded(wa, monkeypatch):
    http(monkeypatch, code=429, payload={}, retry_after="999999")
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(minutes=1))
    assert wa.provider.send(wa.delivery(endpoint), {"text": "Private"}).retry_after == 3600


def test_success_requires_provider_message_id(wa, monkeypatch):
    http(monkeypatch, payload={"messages": []})
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(minutes=1))
    result = wa.provider.send(wa.delivery(endpoint), {"text": "Private"})
    assert not result.accepted and result.ambiguous


@pytest.mark.parametrize("mutation", ["generation", "identity", "consent", "revoked", "tenant", "destination"])
def test_stale_or_unconsented_endpoint_never_sends(wa, mutation):
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(minutes=1))
    delivery = wa.delivery(endpoint)
    if mutation == "generation":
        endpoint.integration_generation += 1
    elif mutation == "identity":
        endpoint.integration_identity = "other"
    elif mutation == "consent":
        endpoint.consented_at = None
    elif mutation == "revoked":
        endpoint.revoked_at = timezone.now()
    elif mutation == "tenant":
        delivery.makerspace_id += 100
    else:
        endpoint.destination = "invalid"
    assert wa.provider.send(delivery, {"text": "Private"}).error_code == "invalid_endpoint"


def test_invalid_credentials_are_not_configured(wa):
    wa.config.set_credentials({**wa.secrets, "phone_number_id": "300/../../attacker"})
    assert wa.provider.test(wa.endpoint()).error_code == "not_configured"


def test_exact_24h_and_future_time_are_not_sessions():
    now = timezone.now()
    assert not in_session_window(SimpleNamespace(last_inbound_at=now - timedelta(hours=24)), now=now)
    assert not in_session_window(SimpleNamespace(last_inbound_at=now + timedelta(seconds=1)), now=now)
    assert in_session_window(SimpleNamespace(last_inbound_at=now - timedelta(hours=23)), now=now)
