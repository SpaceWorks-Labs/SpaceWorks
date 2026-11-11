import json
from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.notification_proofs import start
from apps.integrations.notification_wa_twilio_config import callback_path
from tests.return_helpers import make_space
from .conftest import ACCOUNT, DESTINATION, MESSAGE, SENDER, signature

pytestmark = pytest.mark.django_db


def test_bad_signature_has_no_state_change(wa):
    response = wa.post(params={"Body": "STOP"}, signed=False)
    assert response.status_code == 403
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None and wa.endpoint.last_inbound_at is None


def test_verified_inbound_opens_window_using_public_url_behind_proxy(wa):
    assert wa.post(params={"Body": "Hello", "FutureTwilioField": "also signed"}).status_code == 200
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.last_inbound_at is not None


def test_signed_field_tampering_is_rejected(wa):
    path = callback_path(wa.config, "inbound")
    data = {"AccountSid": ACCOUNT, "MessageSid": MESSAGE, "From": "whatsapp:" + DESTINATION,
            "To": "whatsapp:" + SENDER, "Body": "Hello", "FutureField": "original"}
    signed = signature(path, data)
    data["FutureField"] = "tampered"
    response = APIClient().post(path, urlencode(data), content_type="application/x-www-form-urlencoded",
                               HTTP_X_TWILIO_SIGNATURE=signed)
    assert response.status_code == 403
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.last_inbound_at is None


@pytest.mark.parametrize("word", ["STOP", "UNSUBSCRIBE", " stop "])
def test_stop_revokes_only_whatsapp_consent(wa, word):
    assert wa.post(params={"Body": word}).status_code == 200
    wa.endpoint.refresh_from_db()
    wa.user.refresh_from_db()
    assert wa.endpoint.revoked_at and wa.endpoint.verification_state == "revoked"
    assert wa.user.is_active  # WhatsApp consent never changes authentication standing.
    assert wa.post(params={"Body": word}).status_code == 200


def test_duplicate_inbound_does_not_extend_window(wa):
    assert wa.post(params={"Body": "Hello"}).status_code == 200
    old = timezone.now() - timedelta(hours=2)
    NotificationEndpoint.objects.filter(pk=wa.endpoint.pk).update(last_inbound_at=old)
    assert wa.post(params={"Body": "Hello"}).status_code == 200
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.last_inbound_at == old


def test_replay_cache_failure_is_typed_and_does_not_change_endpoint(wa, monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionError("secret backend details")
    monkeypatch.setattr("apps.integrations.notification_wa_twilio_views.cache.add", fail)
    response = wa.post(params={"Body": "STOP"})
    assert response.status_code == 503 and "secret" not in str(response.data)
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None


@pytest.mark.parametrize("status,state", [("queued", "accepted"), ("sent", "sent"), ("delivered", "delivered"),
    ("read", "read"), ("failed", "failed"), ("undelivered", "failed"), ("accepted", "accepted"),
    ("sending", "accepted"), ("canceled", "failed")])
def test_callback_mapping_including_callback_before_rest_response(wa, status, state):
    assert wa.delivery.state == "retrying"
    assert wa.post("status", {"MessageStatus": status}).status_code == 200
    wa.delivery.refresh_from_db()
    assert wa.delivery.state == state and wa.delivery.provider_id == MESSAGE


def test_out_of_order_duplicate_and_late_failure_cannot_regress_read(wa):
    for status in ("sent", "delivered", "read", "queued", "sent", "failed", "read"):
        assert wa.post("status", {"MessageStatus": status}).status_code == 200
    wa.delivery.refresh_from_db()
    assert wa.delivery.state == "read"


def test_callback_cannot_rebind_provider_message_id(wa):
    wa.delivery.provider_id = "SM" + "5" * 32
    wa.delivery.save()
    assert wa.post("status", {"MessageStatus": "read"}).status_code == 403
    wa.delivery.refresh_from_db()
    assert wa.delivery.provider_id != MESSAGE and wa.delivery.state == "retrying"


@pytest.mark.parametrize("field,value", [("AccountSid", "AC" + "9" * 32),
    ("To", "whatsapp:+14155550000"), ("From", "+14155550123")])
def test_signature_alone_does_not_override_business_account_or_channel(wa, field, value):
    assert wa.post(params={field: value, "Body": "STOP"}).status_code == 403
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None


def test_old_generation_callback_refused_after_rotation(wa):
    path = callback_path(wa.config, "inbound")
    wa.config.generation += 1
    wa.config.save()
    assert wa.post(path=path, params={"Body": "STOP"}).status_code == 404
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None


def test_status_is_scoped_even_when_tenants_share_twilio_account(wa):
    other = ChannelConfiguration.objects.create(makerspace=make_space("wa-other"), channel="whatsapp", provider="twilio",
        enabled=True, personal_enabled=True, integration_identity="other-installation")
    other.set_credentials(wa.credentials)
    other.save()
    path = callback_path(other, "status", wa.delivery.pk)
    assert wa.post("status", {"MessageStatus": "read"}, path=path).status_code == 403
    wa.delivery.refresh_from_db()
    assert wa.delivery.state == "retrying"


def test_stop_does_not_find_endpoint_in_another_tenant(wa):
    other = ChannelConfiguration.objects.create(makerspace=make_space("wa-stop-other"), channel="whatsapp", provider="twilio",
        enabled=True, personal_enabled=True, integration_identity="other-stop-installation")
    other.set_credentials(wa.credentials)
    other.save()
    assert wa.post(path=callback_path(other, "inbound"), params={"Body": "STOP"}).status_code == 200
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None


def test_status_destination_must_match_delivery_endpoint(wa):
    assert wa.post("status", {"MessageStatus": "read", "To": "whatsapp:+14155550999"}).status_code == 403
    wa.delivery.refresh_from_db()
    assert wa.delivery.state == "retrying"


def test_inbound_code_consumes_matching_candidate_once(wa):
    wa.template("notification_opt_in", ["code"], audience="member")
    candidate = "+14155550999"
    challenge, _ = start(wa.user, wa.config, "wa-optin-v1", phone_number=candidate)
    code = json.loads(wa.http.calls[-1][1]["ContentVariables"][0])["1"]
    assert wa.post(params={"From": "whatsapp:" + candidate, "Body": code}).status_code == 200
    challenge.refresh_from_db()
    endpoint = challenge.endpoint
    assert challenge.consumed_at and endpoint.destination == candidate and endpoint.user_id == wa.user.pk
    assert endpoint.last_inbound_at and endpoint.consent_version == "wa-optin-v1"
    assert wa.post(params={"From": "whatsapp:" + candidate, "Body": code}).status_code == 200
    assert NotificationEndpoint.objects.filter(configuration=wa.config, revoked_at=None).count() == 1


@pytest.mark.parametrize("wrong", ["number", "tenant"])
def test_proof_cannot_create_endpoint_for_wrong_number_or_tenant(wa, wrong):
    wa.template("notification_opt_in", ["code"], audience="member")
    challenge, _ = start(wa.user, wa.config, "wa-v1", phone_number="+14155550999")
    code = json.loads(wa.http.calls[-1][1]["ContentVariables"][0])["1"]
    path = None
    if wrong == "tenant":
        other = ChannelConfiguration.objects.create(makerspace=make_space("wa-proof-other"), channel="whatsapp",
            provider="twilio", enabled=True, personal_enabled=True, integration_identity="other")
        other.set_credentials(wa.credentials)
        other.save()
        path = callback_path(other, "inbound")
    response = wa.post(path=path, params={"Body": code})
    assert response.status_code == 400
    challenge.refresh_from_db()
    assert challenge.consumed_at is None and challenge.endpoint_id is None
    if wrong == "number":
        assert challenge.attempts == 1


def test_expired_proof_never_creates_endpoint(wa):
    wa.template("notification_opt_in", ["code"], audience="member")
    challenge, _ = start(wa.user, wa.config, "wa-v1", phone_number=DESTINATION)
    code = json.loads(wa.http.calls[-1][1]["ContentVariables"][0])["1"]
    challenge.expires_at = timezone.now() - timedelta(seconds=1)
    challenge.save(update_fields=["expires_at"])
    assert wa.post(params={"Body": code}).status_code == 400
    challenge.refresh_from_db()
    assert challenge.endpoint_id is None and challenge.attempts == 1


def test_browser_verification_route_cannot_supply_destination(wa):
    api = APIClient()
    api.force_authenticate(wa.user)
    path = reverse("contract-endpoint-start", kwargs={"makerspace_id": wa.space.pk})
    response = api.post(path, {"channel": "whatsapp", "consent": True, "consent_version": "v1",
        "phone_number": DESTINATION, "destination": DESTINATION}, format="json")
    assert response.status_code == 400


def test_charset_parameter_on_form_content_type_is_accepted(wa):
    response = wa.post(params={"Body": "Hello"}, content_type="application/x-www-form-urlencoded; charset=utf-8")
    assert response.status_code == 200
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.last_inbound_at is not None


def test_json_body_is_refused_before_any_change(wa):
    assert wa.post(params={"Body": "STOP"}, content_type="application/json").status_code in {403, 415}
    wa.endpoint.refresh_from_db()
    assert wa.endpoint.revoked_at is None
