from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.integrations.models_contract import NotificationDelivery
from apps.integrations.notification_delivery import claim, record_result
from apps.integrations.notification_providers import ProviderResult
from apps.integrations.notification_wa_meta_reference import client_reference

pytestmark = pytest.mark.django_db


def post_status(wa, delivery, state, *, code=None, reference=None, provider_id="wamid.early"):
    row = {"id": provider_id, "status": state,
           "biz_opaque_callback_data": reference or client_reference(wa.config, delivery)}
    if code is not None:
        row["errors"] = [{"code": code, "message": "Never store provider text"}]
    return wa.post(wa.payload("statuses", [row]))


@pytest.mark.parametrize("state,code,attempt,expected", [
    ("sent", None, 1, "sent"), ("delivered", None, 1, "delivered"),
    ("read", None, 1, "read"), ("failed", 131000, 1, "retrying"),
    ("failed", 131026, 1, "failed"), ("failed", 131000, 4, "failed"),
])
def test_signed_early_status_wins_send_response_and_failure_releases_fallback(wa, monkeypatch, state, code, attempt, expected):
    endpoint = wa.endpoint(last_inbound_at=timezone.now() - timedelta(minutes=1))
    delivery = wa.delivery(endpoint, state="retrying", provider_id="", attempt_count=attempt - 1)
    sending = claim(delivery.pk)
    # Exercise the real shared fallback writer; only substitute the live policy resolver.
    monkeypatch.setattr("apps.integrations.notification_delivery.resolve",
        lambda envelope, fallback=False: [SimpleNamespace(channel="email", endpoint=None)] if fallback else [])
    outbound = []

    def provider_http(method, url, **kwargs):
        assert method == "POST"
        outbound.append(kwargs["json"])
        reference = kwargs["json"]["biz_opaque_callback_data"]
        assert post_status(wa, sending, state, code=code, reference=reference).status_code == 200
        return SimpleNamespace(status_code=200, headers={}, json=lambda: {"messages": [{"id": "wamid.early"}]})

    monkeypatch.setattr("requests.request", provider_http)
    result = wa.provider.send(sending, {"text": "A private notice"})
    assert result.accepted and outbound
    current = record_result(sending, result)
    current.refresh_from_db()
    assert current.state == expected and current.provider_id == "wamid.early"
    assert current.claim_until is None
    assert current.envelope.deliveries.filter(channel="email").exists() == (expected == "failed")
    if expected == "retrying":
        assert current.retryable and current.next_attempt_at > timezone.now()
    assert "Never store" not in current.last_error


def test_reference_cannot_replace_a_bound_provider_id(wa):
    delivery = wa.delivery(wa.endpoint(), attempt_count=1)
    assert post_status(wa, delivery, "read", provider_id="wamid.other").status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == "accepted" and delivery.provider_id == "wamid.test"


@pytest.mark.parametrize("result", [ProviderResult(True, provider_id="wamid.other"),
    ProviderResult(False, retryable=True, error_code="timeout", ambiguous=True)])
def test_early_retry_is_not_overwritten_by_a_conflicting_or_ambiguous_response(wa, result):
    delivery = wa.delivery(wa.endpoint(), state="retrying", provider_id="", attempt_count=0)
    sending = claim(delivery.pk)
    assert post_status(wa, sending, "failed", code=131000).status_code == 200
    current = record_result(sending, result)
    assert current.state == "retrying" and current.provider_id == "wamid.early"
    assert current.retryable and current.next_attempt_at


@pytest.mark.parametrize("bad_reference", ["tampered", "old_generation", "old_attempt"])
def test_untrusted_or_stale_reference_cannot_bind_unrecorded_delivery(wa, bad_reference):
    delivery = wa.delivery(wa.endpoint(), state="retrying", provider_id="", attempt_count=1,
        claim_until=timezone.now() + timedelta(minutes=5))
    reference = client_reference(wa.config, delivery)
    if bad_reference == "tampered":
        reference += "bad"
    elif bad_reference == "old_generation":
        wa.config.generation += 1
        reference = client_reference(wa.config, delivery)
        wa.config.generation -= 1
    else:
        delivery.attempt_count += 1
        delivery.save(update_fields=["attempt_count"])
    assert post_status(wa, delivery, "read", reference=reference).status_code == 200
    delivery.refresh_from_db()
    assert delivery.state == "retrying" and delivery.provider_id == ""


def test_retry_has_new_message_correlation_and_ignores_old_attempt(wa):
    delivery = wa.delivery(wa.endpoint(), state="retrying", provider_id="", attempt_count=0)
    first = claim(delivery.pk)
    old_reference = client_reference(wa.config, first)
    post_status(wa, first, "failed", code=131000)
    NotificationDelivery.objects.filter(pk=delivery.pk).update(next_attempt_at=timezone.now() - timedelta(seconds=1))
    second = claim(delivery.pk)
    assert second.attempt_count == 2 and second.provider_id == ""
    post_status(wa, second, "failed", code=131026, reference=old_reference)
    second.refresh_from_db()
    assert second.state == "retrying" and second.claim_until
    assert post_status(wa, second, "delivered", provider_id="wamid.second").status_code == 200
    assert record_result(first, ProviderResult(True, provider_id="wamid.early")).provider_id == "wamid.second"
    assert record_result(second, ProviderResult(True, provider_id="wamid.second")).state == "delivered"
