"""Send switches preserve callbacks; module uninstall retires their generation."""
import json

import pytest

from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.notification_proofs import start
from apps.integrations.notification_wa_twilio_config import callback_path
from tests.p2_wa_twilio.conftest import DESTINATION

pytestmark = pytest.mark.django_db
DISABLED = ["enabled", "personal_enabled", "notifications"]


def disable(wa, switch):
    if switch == "notifications":
        wa.space.enabled_modules = [key for key in wa.space.enabled_modules if key != "notifications"]
        wa.space.save(update_fields=["enabled_modules"])
        # Migration 0036 retires the installation on uninstall, unlike send switches.
        # Leave the fixture's generation stale: these callbacks were already in flight.
        current = ChannelConfiguration.objects.get(pk=wa.config.pk)
        assert current.generation == wa.config.generation + 1
        endpoints = NotificationEndpoint.objects.filter(configuration=wa.config)
        assert not endpoints.filter(revoked_at=None).exists()
        assert not endpoints.exclude(verification_state="revoked").exists()
    else:
        setattr(wa.config, switch, False)
        wa.config.save(update_fields=[switch])


@pytest.mark.parametrize("switch", DISABLED)
@pytest.mark.parametrize("word", ["STOP", " unsubscribe "])
def test_disabled_delivery_still_revokes_consent(twilio_wa, switch, word):
    wa = twilio_wa
    generation = wa.config.generation
    path = callback_path(wa.config, "inbound")
    disable(wa, switch)
    expected_status = 404 if switch == "notifications" else 200
    assert wa.post(params={"Body": word}).status_code == expected_status
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at and wa.endpoint.verification_state == "revoked"
    wa.config.refresh_from_db()
    assert wa.config.generation == generation + (switch == "notifications")
    # Switch-only re-enablement must never resurrect consent.
    wa.config.enabled = wa.config.personal_enabled = True
    wa.config.save(update_fields=["enabled", "personal_enabled"])
    assert not wa.provider.valid_endpoint(wa.endpoint)
    # Retry the original URL, including after uninstall has advanced the generation.
    assert wa.post(params={"Body": word}, path=path).status_code == expected_status
    assert not wa.http.calls


@pytest.mark.parametrize("switch", DISABLED)
@pytest.mark.parametrize("status,state", [("delivered", "delivered"), ("read", "read"), ("failed", "failed")])
def test_disabled_delivery_still_records_in_flight_status(twilio_wa, switch, status, state):
    wa = twilio_wa
    original_state = wa.delivery.state
    disable(wa, switch)
    expected_status = 404 if switch == "notifications" else 200
    expected_state = original_state if switch == "notifications" else state
    assert wa.post("status", {"MessageStatus": status}).status_code == expected_status
    wa.delivery.refresh_from_db()
    assert wa.delivery.state == expected_state
    assert wa.post("status", {"MessageStatus": "queued"}).status_code == expected_status
    wa.delivery.refresh_from_db()
    assert wa.delivery.state == expected_state


@pytest.mark.parametrize("switch", DISABLED)
def test_disabling_delivery_still_blocks_new_consent_proofs(twilio_wa, switch):
    wa = twilio_wa
    wa.template("notification_opt_in", ["code"], audience="member")
    challenge, _ = start(wa.user, wa.config, "v1", phone_number=DESTINATION)
    code = json.loads(wa.http.calls[-1][1]["ContentVariables"][0])["1"]
    disable(wa, switch)
    assert wa.post(params={"Body": code}).status_code == (404 if switch == "notifications" else 403)
    challenge.refresh_from_db()
    wa.endpoint.refresh_from_db()
    assert challenge.consumed_at is None and challenge.endpoint_id is None
    assert wa.endpoint.last_inbound_at is None
    assert not wa.provider.send(wa.delivery, {"text": "Hello"}).accepted


@pytest.mark.parametrize("kind", ["inbound", "status"])
@pytest.mark.parametrize("invalid", ["signature", "generation", "account", "business", "tenant"])
def test_disabled_callbacks_keep_signature_and_installation_binding(twilio_wa, kind, invalid):
    wa = twilio_wa
    disable(wa, "enabled")
    path = callback_path(wa.config, kind, wa.delivery.pk if kind == "status" else None)
    params = {"Body": "STOP"} if kind == "inbound" else {"MessageStatus": "read"}
    if invalid == "generation":
        wa.config.generation += 1
        wa.config.save(update_fields=["generation"])
    elif invalid == "account":
        params["AccountSid"] = "AC" + "9" * 32
    elif invalid == "business":
        params["To" if kind == "inbound" else "From"] = "whatsapp:+14155550999"
    elif invalid == "tenant":
        from tests.return_helpers import make_space
        other = ChannelConfiguration.objects.create(makerspace=make_space("disabled-wa-other"),
            channel="whatsapp", provider="twilio", integration_identity="other")
        other.set_credentials(wa.credentials)
        other.save()
        path = callback_path(other, kind, wa.delivery.pk if kind == "status" else None)
    response = wa.post(kind, params, path=path, signed=invalid != "signature")
    assert response.status_code == (404 if invalid == "generation" else 200 if invalid == "tenant" and kind == "inbound" else 403)
    wa.endpoint.refresh_from_db()
    wa.delivery.refresh_from_db()
    assert wa.endpoint.revoked_at is None and wa.delivery.state == "retrying"


def test_rotation_between_authentication_and_lock_rejects_callback(twilio_wa, monkeypatch):
    from apps.integrations.notification_wa_twilio import TwilioWhatsAppProvider
    wa = twilio_wa
    disable(wa, "enabled")
    original = TwilioWhatsAppProvider.verify_callback
    calls = 0

    def rotate(provider, request):
        nonlocal calls
        event = original(provider, request)
        calls += 1
        if calls == 1:
            ChannelConfiguration.objects.filter(pk=wa.config.pk).update(generation=wa.config.generation + 1)
        return event

    monkeypatch.setattr(TwilioWhatsAppProvider, "verify_callback", rotate)
    assert wa.post(params={"Body": "STOP"}).status_code == 403
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None
