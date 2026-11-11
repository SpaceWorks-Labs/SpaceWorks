import json
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.integrations.notification_proofs import start
from apps.integrations.notification_providers import provider_for

pytestmark = pytest.mark.django_db


def test_registered_and_credentials_are_encrypted(wa):
    assert type(provider_for(wa.config)) is type(wa.provider)
    assert wa.credentials["auth_token"] not in wa.config.credentials
    assert wa.config.get_credentials() == wa.credentials


def test_outside_window_requires_approved_binding(wa):
    assert wa.provider.send(wa.delivery, {"text": "Private body"}).error_code == "template_required"
    binding = wa.template(approved=False)
    assert wa.provider.send(wa.delivery, {"text": "Private body"}).error_code == "template_required"
    assert not wa.http.calls
    binding.approved = True
    binding.save()
    result = wa.provider.send(wa.delivery, {"text": "Private body", "tool": "Not safe context"})
    assert result.accepted
    req, payload = wa.http.calls[-1]
    assert "Body" not in payload and json.loads(payload["ContentVariables"][0]) == {"1": "Drill"}
    assert payload["ContentSid"] == [binding.template_name]
    assert payload["StatusCallback"][0].endswith(f"/{wa.config.generation}/status/{wa.delivery.pk}")
    assert req.full_url.startswith("https://api.twilio.com/2010-04-01/Accounts/")


@pytest.mark.parametrize("hours,freeform", [(1, True), (24, False), (25, False), (-1, False)])
def test_window_is_strict_and_never_opened_by_sends(wa, hours, freeform):
    wa.template()
    wa.endpoint.last_inbound_at = timezone.now() - timedelta(hours=hours)
    wa.endpoint.save(update_fields=["last_inbound_at"])
    assert wa.provider.send(wa.delivery, {"text": "Private body"}).accepted
    assert ("Body" in wa.http.calls[-1][1]) is freeform
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.last_inbound_at < timezone.now() if hours >= 0 else wa.endpoint.last_inbound_at > timezone.now()


@pytest.mark.parametrize("variable", ["missing", "nested"])
def test_template_cannot_use_rendered_or_nested_context(wa, variable):
    wa.template(variables=[variable])
    wa.envelope.context = {"nested": {"secret": "hidden"}}
    result = wa.provider.send(wa.delivery, {"text": "Body", "missing": "rendered"})
    assert result.error_code == "template_required" and not wa.http.calls


@pytest.mark.parametrize("change", ["revoked", "generation", "tenant", "disabled", "standing"])
def test_live_endpoint_or_installation_changes_fail_closed(wa, change):
    wa.template()
    if change == "revoked":
        wa.endpoint.revoked_at = timezone.now()
    elif change == "generation":
        wa.config.generation += 1
    elif change == "tenant":
        wa.delivery.makerspace_id += 99
    elif change == "disabled":
        wa.config.personal_enabled = False
    else:
        wa.user.is_active = False
        wa.user.save(update_fields=["is_active"])
    assert wa.provider.send(wa.delivery, {"text": "Body"}).error_code == "invalid_endpoint"
    assert not wa.http.calls


def test_test_always_uses_approved_template_to_verified_endpoint(wa):
    wa.endpoint.last_inbound_at = timezone.now()
    assert wa.provider.test(wa.endpoint).error_code == "template_required"
    wa.template("notification_test", [], audience="member")
    assert wa.provider.test(wa.endpoint).accepted
    assert "Body" not in wa.http.calls[-1][1]
    wa.endpoint.revoked_at = timezone.now()
    assert not wa.provider.test(wa.endpoint).accepted


def test_challenge_sends_code_but_never_creates_endpoint(wa):
    from apps.integrations.models_endpoints import NotificationEndpoint
    wa.template("notification_opt_in", ["code"], audience="member")
    count = NotificationEndpoint.objects.count()
    challenge, result = start(wa.user, wa.config, "wa-v1", phone_number="+14155550999")
    assert challenge.endpoint_id is None and NotificationEndpoint.objects.count() == count
    assert "code" not in result and "instructions" in result
    payload = wa.http.calls[-1][1]
    assert payload["To"] == ["whatsapp:+14155550999"]
    code = json.loads(payload["ContentVariables"][0])["1"]
    assert code not in challenge.code_digest and len(code) == 43


def test_invalid_credentials_are_safe_at_send_boundary(wa):
    wa.template()
    wa.config.set_credentials({"account_sid": "bad", "auth_token": "secret"})
    assert wa.provider.send(wa.delivery, {"text": "Body"}).error_code == "not_configured"
    assert not wa.http.calls
