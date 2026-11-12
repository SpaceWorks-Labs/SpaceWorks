import hashlib
import hmac
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint
from apps.integrations.notification_wa_meta_callbacks import callback_event
from apps.integrations.notification_wa_meta_views import MetaWebhookView
from tests.return_helpers import make_space, make_user

pytestmark = pytest.mark.django_db


def test_handshake_echoes_plain_challenge(wa):
    request = APIRequestFactory().get("/meta/webhook", {"hub.mode": "subscribe",
        "hub.verify_token": "verify-me", "hub.challenge": "001234"})
    response = MetaWebhookView.as_view()(request, makerspace_id=wa.space.pk,
        generation=wa.config.generation, phone_number_id="300")
    assert response.status_code == 200 and response.content == b"001234"
    assert response["Content-Type"].startswith("text/plain")


@pytest.mark.parametrize("mode,token,phone,generation", [
    ("wrong", "verify-me", "300", 1), ("subscribe", "wrong", "300", 1),
    ("subscribe", "verify-me", "999", 1), ("subscribe", "verify-me", "300", 100),
])
def test_handshake_rejects_wrong_binding(wa, mode, token, phone, generation):
    request = APIRequestFactory().get("/meta/webhook", {"hub.mode": mode,
        "hub.verify_token": token, "hub.challenge": "123"})
    response = MetaWebhookView.as_view()(request, makerspace_id=wa.space.pk,
        generation=generation, phone_number_id=phone)
    assert response.status_code in {403, 404}


def test_signature_is_checked_before_json(wa, monkeypatch):
    original = json.loads
    def loads(raw, *args, **kwargs):
        if raw == b"not-json":
            pytest.fail("Parsed before signature verification")
        return original(raw, *args, **kwargs)
    monkeypatch.setattr("apps.integrations.notification_wa_meta_callbacks.json.loads",
                        loads)
    response = wa.post(None, raw=b"not-json", signature="sha256=" + "0" * 64)
    assert response.status_code == 403


@pytest.mark.parametrize("signature", ["invalid", "sha256=xyz", "sha256=" + "0" * 64])
def test_unsigned_callback_cannot_mutate(wa, signature):
    endpoint = wa.endpoint()
    response = wa.post(wa.payload("messages", [wa.message("STOP")]), signature=signature)
    endpoint.refresh_from_db()
    assert response.status_code == 403 and endpoint.revoked_at is None and endpoint.last_inbound_at is None


def test_modified_raw_body_fails_signature(wa):
    body = json.dumps(wa.payload("messages", [wa.message()])).encode()
    signature = "sha256=" + hmac.new(wa.secrets["app_secret"].encode(), body, hashlib.sha256).hexdigest()
    assert wa.post(None, raw=body + b" ", signature=signature).status_code == 403


def test_signed_malformed_json_is_refused(wa):
    assert wa.post(None, raw=b"{invalid").status_code == 403


@pytest.mark.parametrize("state", ["sent", "delivered", "read", "failed"])
def test_status_mapping(wa, state):
    delivery = wa.delivery(wa.endpoint())
    assert wa.post(wa.payload("statuses", [{"id": delivery.provider_id, "status": state}])).status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == state


def test_batch_and_replays_preserve_monotonic_success(wa):
    delivery = wa.delivery(wa.endpoint())
    rows = [{"id": delivery.provider_id, "status": value} for value in ["read", "sent", "failed", "delivered"]]
    for _ in range(2):
        assert wa.post(wa.payload("statuses", rows)).status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == "read"


def test_status_never_opens_a_session(wa):
    endpoint = wa.endpoint()
    delivery = wa.delivery(endpoint)
    wa.post(wa.payload("statuses", [{"id": delivery.provider_id, "status": "delivered"}]))
    endpoint.refresh_from_db()
    assert endpoint.last_inbound_at is None


@pytest.mark.parametrize("phone,business", [("999", "200"), ("300", "999")])
def test_body_cannot_select_another_tenant(wa, phone, business):
    endpoint = wa.endpoint()
    assert wa.post(wa.payload("messages", [wa.message("STOP")], phone=phone, business=business)).status_code == 200
    endpoint.refresh_from_db()
    assert endpoint.revoked_at is None


def test_same_app_secret_does_not_cross_tenants(wa):
    endpoint = wa.endpoint()
    other = make_space("meta-other")
    config = ChannelConfiguration.objects.create(makerspace=other, channel="whatsapp", provider="meta",
        enabled=True, personal_enabled=True, integration_identity="other-meta")
    config.set_credentials({**wa.secrets, "phone_number_id": "301"})
    config.save(update_fields=["credentials"])
    response = wa.post(wa.payload("messages", [wa.message("STOP")]), tenant=other.pk, phone="301")
    endpoint.refresh_from_db()
    assert response.status_code == 200 and endpoint.revoked_at is None


def test_old_generation_rejects_even_with_current_app_secret(wa):
    endpoint = wa.endpoint()
    old = wa.config.generation
    wa.config.generation += 1
    wa.config.save(update_fields=["generation"])
    assert wa.post(wa.payload("messages", [wa.message("STOP")]), generation=old).status_code == 403  # a stale generation is indistinguishable from a bad signature
    endpoint.refresh_from_db()
    assert endpoint.revoked_at is None


@pytest.mark.parametrize("keyword", ["STOP", "unsubscribe", "Opt Out", "BLOCK"])
def test_opt_out_revokes(wa, keyword):
    endpoint = wa.endpoint()
    assert wa.post(wa.payload("messages", [wa.message(keyword)])).status_code == 200
    endpoint.refresh_from_db()
    assert endpoint.revoked_at and endpoint.verification_state == "revoked"


def test_provider_preference_stop_revokes_and_resume_does_not_reconsent(wa):
    endpoint = wa.endpoint()
    for value in ("stop", "resume"):
        row = {"wa_id": "15551234567", "category": "marketing_messages", "value": value}
        assert wa.post(wa.payload("user_preferences", [row], field="user_preferences")).status_code == 200
    endpoint.refresh_from_db()
    assert endpoint.revoked_at


def test_provider_opt_out_failure_revokes(wa):
    endpoint = wa.endpoint()
    delivery = wa.delivery(endpoint)
    row = {"id": delivery.provider_id, "recipient_id": "15551234567", "status": "failed", "errors": [{"code": 131050}]}
    assert wa.post(wa.payload("statuses", [row])).status_code == 200
    endpoint.refresh_from_db()
    delivery.refresh_from_db()
    assert endpoint.revoked_at and delivery.last_error == "blocked"


@pytest.mark.parametrize("code", [130429, 131016])
def test_transient_failure_callbacks_retry_before_fallback(wa, code):
    delivery = wa.delivery(wa.endpoint(), attempt_count=1)
    row = {"id": delivery.provider_id, "status": "failed", "errors": [{"code": code}]}
    assert wa.post(wa.payload("statuses", [row])).status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == "retrying" and delivery.retryable and delivery.next_attempt_at
    assert not delivery.envelope.deliveries.filter(channel="email").exists()
    scheduled = delivery.next_attempt_at
    assert wa.post(wa.payload("statuses", [row])).status_code == 200
    delivery.refresh_from_db()
    assert delivery.next_attempt_at == scheduled


def test_transient_failure_cannot_regress_read(wa):
    delivery = wa.delivery(wa.endpoint(), state="read", attempt_count=1)
    row = {"id": delivery.provider_id, "status": "failed", "errors": [{"code": 130429}]}
    assert wa.post(wa.payload("statuses", [row])).status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == "read" and not delivery.retryable


def test_callback_retry_budget_is_bounded(wa, monkeypatch):
    fallback = []
    monkeypatch.setattr("apps.integrations.notification_delivery.fallback_if_exhausted", lambda envelope: fallback.append(envelope.pk))
    monkeypatch.setattr("apps.integrations.notification_outbox.enqueue", lambda pk: None)
    delivery = wa.delivery(wa.endpoint(), attempt_count=4)
    row = {"id": delivery.provider_id, "status": "failed", "errors": [{"code": 130429}]}
    assert wa.post(wa.payload("statuses", [row])).status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == "failed" and not delivery.retryable and fallback == [delivery.envelope_id]


def test_closed_source_gate_returns_typed_error_without_mutation(wa, monkeypatch):
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    def closed(*args, **kwargs):
        raise SourceMigrationGateClosed("closed")
    monkeypatch.setattr("apps.integrations.notification_wa_meta_ingress.tenant_write", closed)
    endpoint = wa.endpoint()
    response = wa.post(wa.payload("messages", [wa.message("STOP")]))
    endpoint.refresh_from_db()
    assert response.status_code == 423 and response.data["code"] == "tenant_migration_quiesced"
    assert endpoint.revoked_at is None


def test_batch_rejects_invalid_shapes_without_partial_application(wa):
    endpoint = wa.endpoint()
    response = wa.post(wa.payload("messages", [wa.message("STOP"), "invalid"]))
    endpoint.refresh_from_db()
    assert response.status_code == 400 and endpoint.revoked_at is None


def test_authenticated_inbound_uses_event_time_and_never_rewinds(wa):
    endpoint = wa.endpoint()
    newer = int((timezone.now() - timedelta(hours=1)).timestamp())
    older = newer - 3600
    for timestamp in (newer, older, newer):
        assert wa.post(wa.payload("messages", [wa.message(timestamp=timestamp)])).status_code == 200
    endpoint.refresh_from_db()
    assert int(endpoint.last_inbound_at.timestamp()) == newer


def test_future_inbound_cannot_open_window(wa):
    endpoint = wa.endpoint()
    future = int((timezone.now() + timedelta(days=1)).timestamp())
    wa.post(wa.payload("messages", [wa.message(timestamp=future)]))
    endpoint.refresh_from_db()
    assert endpoint.last_inbound_at is None


def test_matching_inbound_consumes_proof_once(wa):
    challenge, code = wa.challenge()
    body = wa.payload("messages", [wa.message(code)])
    assert wa.post(body).status_code == 200
    challenge.refresh_from_db()
    endpoint = NotificationEndpoint.objects.get(pk=challenge.endpoint_id)
    assert challenge.consumed_at and endpoint.user == wa.user and endpoint.last_inbound_at
    assert wa.post(body).status_code == 200
    assert NotificationEndpoint.objects.filter(configuration=wa.config).count() == 1


def test_matching_phone_proof_adds_own_binding_without_stealing_another_accounts_endpoint(wa):
    endpoint = wa.endpoint()
    challenge, code = wa.challenge(user=make_user("meta-other-owner"))
    assert wa.post(wa.payload("messages", [wa.message(code)])).status_code == 200
    challenge.refresh_from_db()
    endpoint.refresh_from_db()
    assert challenge.consumed_at and endpoint.revoked_at is None
    assert endpoint.user_id == wa.user.pk
    linked = NotificationEndpoint.objects.get(pk=challenge.endpoint_id)
    assert linked.user_id == challenge.user_id and linked.pk != endpoint.pk
    assert linked.identity_digest == endpoint.identity_digest
    assert NotificationEndpoint.objects.filter(configuration=wa.config).count() == 2


def test_unknown_provider_message_id_cannot_change_delivery(wa):
    delivery = wa.delivery(wa.endpoint())
    assert wa.post(wa.payload("statuses", [{"id": "wamid.unknown", "status": "read"}])).status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == "accepted"


@pytest.mark.parametrize("failure", ["sender", "expired", "wrong_code", "generation", "module"])
def test_invalid_proof_creates_no_endpoint(wa, failure):
    challenge, code = wa.challenge()
    sender = "15551234567"
    if failure == "sender":
        sender = "15559999999"
    elif failure == "expired":
        challenge.expires_at = timezone.now() - timedelta(minutes=1)
        challenge.save(update_fields=["expires_at"])
    elif failure == "wrong_code":
        code = "B" * 43
    elif failure == "generation":
        challenge.integration_generation += 1
        challenge.save(update_fields=["integration_generation"])
    else:
        wa.space.enabled_modules = []
        wa.space.save(update_fields=["enabled_modules"])
    # Removing notifications rotates the installation in the database; the old
    # generation URL must be refused before it can consume an outstanding proof.
    expected_status = 403 if failure == "module" else 200  # refused as a bad callback, not a 404 oracle
    assert wa.post(wa.payload("messages", [wa.message(code, sender=sender)])).status_code == expected_status
    assert not NotificationEndpoint.objects.filter(configuration=wa.config).exists()


def test_browser_code_is_not_a_provider_callback(wa):
    request = SimpleNamespace(body=b"{}", headers={}, data={"code": "A" * 43})
    assert callback_event(wa.config, request) is None


def test_webhook_is_throttled(wa):
    response = None
    for _ in range(121):
        response = wa.post(wa.payload("messages", []))
    assert response.status_code == 429


def test_signed_stop_without_timestamp_still_revokes(wa):
    endpoint = wa.endpoint()
    row = wa.message("STOP")
    row.pop("timestamp")
    assert wa.post(wa.payload("messages", [row])).status_code == 200
    endpoint.refresh_from_db()
    assert endpoint.revoked_at and endpoint.verification_state == "revoked"


def test_small_clock_skew_still_consumes_proof_and_clamps_to_now(wa):
    challenge, code = wa.challenge()
    skewed = int((timezone.now() + timedelta(seconds=60)).timestamp())
    assert wa.post(wa.payload("messages", [wa.message(code, timestamp=skewed)])).status_code == 200
    challenge.refresh_from_db()
    endpoint = NotificationEndpoint.objects.get(pk=challenge.endpoint_id)
    assert endpoint.last_inbound_at <= timezone.now()


@pytest.mark.parametrize("tenant", [0, -1])
def test_non_positive_tenant_is_refused_not_a_server_error(wa, tenant):
    request = APIRequestFactory().post("/meta/webhook", data=b"{}", content_type="application/json")
    response = MetaWebhookView.as_view()(request, makerspace_id=tenant,
        generation=wa.config.generation, phone_number_id="300")
    assert response.status_code == 403
