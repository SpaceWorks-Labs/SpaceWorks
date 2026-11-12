"""Keep send-switch callbacks live while rejecting installations retired by uninstall."""
import pytest

from .test_twilio_disabled_callbacks import DISABLED, disable

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("switch", DISABLED)
@pytest.mark.parametrize("kind", ["message", "preference", "failure"])
def test_meta_consent_withdrawals_ignore_send_switches(meta_wa, switch, kind):
    wa = meta_wa
    endpoint = wa.endpoint()
    delivery = wa.delivery(endpoint)
    original_state, original_error = delivery.state, delivery.last_error
    disable(wa, switch)
    if kind == "message":
        payload = wa.payload("messages", [wa.message("STOP")])
    elif kind == "preference":
        payload = wa.payload("user_preferences", [{"wa_id": "15551234567", "value": "stop"}], field="user_preferences")
    else:
        payload = wa.payload("statuses", [{"id": delivery.provider_id, "recipient_id": "15551234567",
            "status": "failed", "errors": [{"code": 131050}]}])
    expected_status = 403 if switch == "notifications" else 200
    assert wa.post(payload).status_code == expected_status
    endpoint.refresh_from_db()
    assert endpoint.revoked_at and endpoint.verification_state == "revoked"
    assert wa.post(payload).status_code == expected_status
    if kind == "failure":
        delivery.refresh_from_db()
        if switch == "notifications":
            assert (delivery.state, delivery.last_error) == (original_state, original_error)
        else:
            assert delivery.state == "failed" and delivery.last_error == "blocked"


@pytest.mark.parametrize("switch", DISABLED)
@pytest.mark.parametrize("state", ["delivered", "read", "failed"])
def test_meta_in_flight_status_ignores_send_switches(meta_wa, switch, state):
    wa = meta_wa
    delivery = wa.delivery(wa.endpoint())
    original_state = delivery.state
    disable(wa, switch)
    response = wa.post(wa.payload("statuses", [{"id": delivery.provider_id, "status": state}]))
    assert response.status_code == (403 if switch == "notifications" else 200)
    delivery.refresh_from_db()
    assert delivery.state == (original_state if switch == "notifications" else state)


@pytest.mark.parametrize("switch", DISABLED)
def test_meta_proof_stays_disabled(meta_wa, switch):
    wa = meta_wa
    challenge, code = wa.challenge()
    disable(wa, switch)
    response = wa.post(wa.payload("messages", [wa.message(code)]))
    assert response.status_code == (403 if switch == "notifications" else 200)
    challenge.refresh_from_db()
    assert challenge.consumed_at is None and challenge.endpoint_id is None


@pytest.mark.parametrize("invalid", ["signature", "generation", "business", "phone"])
def test_meta_disabled_callbacks_keep_authentication_binding(meta_wa, invalid):
    wa = meta_wa
    endpoint = wa.endpoint()
    disable(wa, "enabled")
    kwargs = {}
    if invalid == "signature":
        kwargs["signature"] = "sha256=" + "0" * 64
    if invalid == "generation":
        kwargs["generation"] = wa.config.generation + 1
    payload = wa.payload("messages", [wa.message("STOP")],
        business="999" if invalid == "business" else "200", phone="999" if invalid == "phone" else "300")
    response = wa.post(payload, **kwargs)
    assert response.status_code == (403 if invalid in ("signature", "generation") else 200)
    endpoint.refresh_from_db()
    assert endpoint.revoked_at is None
