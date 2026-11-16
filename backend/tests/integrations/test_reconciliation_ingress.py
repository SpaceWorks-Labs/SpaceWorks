from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.db import transaction
from django.utils import timezone

from apps.integrations.models_cutover import NotificationIngress
from apps.integrations.models_messaging_consent import MessagingSuppression
from apps.integrations.notification_ingress import accept_legacy, process
from apps.integrations.notification_delivery import apply_callback, claim, record_result
from apps.integrations.notification_providers import CallbackEvent, ProviderResult
from apps.integrations.messaging.protections import recipient_hash
from .reconciliation_helpers import account, delivery, space

pytestmark = pytest.mark.django_db


def inbound(**kwargs):
    return accept_legacy(provider="twilio", channel="sms", sender_key="twilio:AC:sender",
        dedupe_id="SM-stop", kind="inbound", payload={"stop": True, "phone_hash": recipient_hash("phone", "+14155550123")}, **kwargs)


def test_receipt_only_stop_is_durable_encrypted_deduplicated_and_not_reapplied(receipt_only_cutover):
    row = inbound()
    assert NotificationIngress.objects.count() == 1
    row.refresh_from_db()
    assert row.state == "pending" and row.protection_applied
    assert row.payload.startswith("fernet:") and "phone_hash" not in row.payload
    suppression = MessagingSuppression.objects.get()
    suppression.lifted_at = timezone.now()
    suppression.save(update_fields=["lifted_at"])
    assert inbound().pk == row.pk
    assert not MessagingSuppression.objects.filter(lifted_at=None).exists()
    assert process(row.pk) is False


def test_stop_suppression_failure_cannot_acknowledge_receipt(receipt_only_cutover, monkeypatch):
    monkeypatch.setattr("apps.integrations.messaging.stops.suppress_recipient", Mock(side_effect=RuntimeError("DB unavailable")))
    with pytest.raises(RuntimeError):
        inbound()
    assert not NotificationIngress.objects.exists()


def test_journal_survives_processing_failure_and_replay_is_idempotent(receipt_only_cutover, monkeypatch):
    row = inbound()
    receipt_only_cutover.route = "canonical"
    receipt_only_cutover.save(update_fields=["route"])
    apply = Mock(side_effect=RuntimeError("processor interrupted"))
    monkeypatch.setattr("apps.integrations.notification_ingress_apply.apply", apply)
    assert process(row.pk) is False
    row.refresh_from_db()
    assert row.state == "held"
    apply.side_effect = None
    apply.return_value = True
    assert process(row.pk) is True
    assert process(row.pk) is True
    assert apply.call_count == 2


@pytest.mark.parametrize("observations", [("delivered", "failed"), ("failed", "delivered")])
def test_callbacks_are_monotonic_and_keep_failure_evidence(observations):
    tenant = space()
    row = delivery(tenant, account(), state="accepted", provider_id="SM1", sender_key="sender")
    config = SimpleNamespace(makerspace=tenant, channel="sms", provider="twilio", generation=0,
        integration_identity="", sender_key="sender")
    for observed in observations:
        apply_callback(config, CallbackEvent(provider_id="SM1", state=observed,
            provider_timestamp=str(int(timezone.now().timestamp()))))
    row.refresh_from_db()
    assert row.state == "delivered" and row.failed_at is not None and row.delivered_at is not None


def test_callback_cannot_cross_sender_generation_or_tenant():
    tenant, other = space(), space("other")
    row = delivery(tenant, account(), state="accepted", provider_id="SM1", integration_generation=2)
    for target, generation in [(other, 2), (tenant, 3)]:
        config = SimpleNamespace(makerspace=target, channel="sms", provider="twilio",
            generation=generation, integration_identity="")
        assert not apply_callback(config, CallbackEvent(provider_id="SM1", state="delivered"))
    row.refresh_from_db()
    assert row.state == "accepted"


def test_expired_addressed_lease_and_ambiguous_send_are_held_not_retried():
    tenant, user = space(), account()
    expired = delivery(tenant, user, attempt_count=4, claim_until=timezone.now() - timedelta(seconds=1))
    assert claim(expired.pk) is None
    expired.refresh_from_db()
    assert expired.state == "held"
    row = delivery(tenant, user, number=2, attempt_count=1)
    record_result(row, ProviderResult(False, retryable=True, ambiguous=True, error_code="timeout"))
    row.refresh_from_db()
    assert row.state == "held" and not row.retryable and row.next_attempt_at is None
    assert claim(row.pk) is None


def test_terminal_historical_rows_never_acquire_send_authority():
    tenant = space()
    row = delivery(tenant, account(), state="failed", historical=True, retryable=True)
    assert claim(row.pk) is None


def test_early_21610_holds_the_sender_until_exact_delivery_is_known(receipt_only_cutover):
    from apps.integrations.messaging.protections import suppressed
    tenant, user = space(), account()
    sender = "twilio:AC:sender"
    digest = recipient_hash("phone", "+14155550123")
    receipt = accept_legacy(provider="twilio", channel="sms", sender_key=sender, makerspace_id=tenant.pk,
        dedupe_id="SM-early:failed", kind="status", payload={"message_id": "SM-early", "status": "failed", "error_code": "21610"})
    assert suppressed("sms", sender, recipient_hash("phone", "+14155550999"))
    row = delivery(tenant, user, state="accepted", provider_id="SM-early", sender_key=sender,
        recipient_phone_hash=digest)
    receipt_only_cutover.route = "canonical"
    receipt_only_cutover.save(update_fields=["route"])
    assert process(receipt.pk)
    assert suppressed("sms", sender, digest)
    assert not suppressed("sms", sender, recipient_hash("phone", "+14155550999"))
    row.refresh_from_db()
    assert row.state == "failed" and row.failed_at is None  # Provider supplied no timestamp.
