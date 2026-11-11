"""FM regressions: recovery fairness, proof ordering and retired-target facts."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_cutover import NotificationProviderReference
from apps.integrations.models_endpoints import ChannelConfiguration, NotificationEndpoint, NotificationEndpointChallenge
from apps.integrations.models_messaging_consent import MessagingConsent, MessagingSuppression
from apps.integrations.notification_delivery import apply_callback, claim
from apps.integrations.notification_ingress import accept_callback, accept_legacy, process
from apps.integrations.notification_proofs import consume, digest
from apps.integrations.notification_providers import CallbackEvent, EndpointProof
from apps.integrations.notification_provider_references import remember
from apps.integrations.notification_whatsapp_consent import proof_receipt
from apps.integrations.messaging.protections import recipient_hash
from .reconciliation_helpers import account, delivery, space

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("channel", ["sms", "whatsapp", "native_push"])
def test_holding_expired_claim_clears_parent_schedule(channel):
    # A claim leaves the leg in its pre-claim state; an expired in-flight lease
    # is an unknown provider outcome and is held, never re-claimed.
    row = delivery(space(), account(), channel=channel, state="retrying", attempt_count=1,
        claim_until=timezone.now() - timedelta(seconds=1), next_attempt_at=timezone.now())
    assert claim(row.pk) is None
    row.refresh_from_db()
    assert row.state == "held" and not row.retryable
    assert row.claim_until is None and row.next_attempt_at is None


@pytest.mark.parametrize("channel", ["sms", "whatsapp", "native_push"])
def test_callback_accepted_leg_keeps_progress_and_drops_its_stale_lease(channel):
    # A callback proved acceptance while the lease was live. Progress is monotonic:
    # it never drops to held, and the stale lease no longer makes the leg runnable.
    from apps.integrations.notification_tasks import runnable_deliveries
    row = delivery(space(), account(), channel=channel, state="accepted", attempt_count=1,
        claim_until=timezone.now() - timedelta(seconds=1), next_attempt_at=timezone.now())
    assert claim(row.pk) is None
    row.refresh_from_db()
    assert row.state == "accepted" and row.attempt_count == 1
    assert row.claim_until is None and row.next_attempt_at is None
    assert not runnable_deliveries(NotificationDelivery.objects.filter(pk=row.pk)).exists()


@pytest.mark.parametrize("processed", [True, False])
def test_two_hundred_legacy_held_claims_do_not_starve_sweeper(monkeypatch, processed):
    from apps.integrations.notification_tasks import sweep_notification_outbox
    tenant, user, expired = space(), account(), timezone.now() - timedelta(minutes=1)
    for number in range(200):
        delivery(tenant, user, number=number, state="held", claim_until=expired, next_attempt_at=expired)
    if processed:
        NotificationEnvelope.objects.update(processed_at=timezone.now())
    later = delivery(tenant, user, number=201, next_attempt_at=expired)
    later.envelope.processed_at = timezone.now()
    later.envelope.save(update_fields=["processed_at"])
    active = delivery(tenant, user, number=202, claim_until=timezone.now() + timedelta(minutes=5))
    active.envelope.processed_at = timezone.now()
    active.envelope.save(update_fields=["processed_at"])
    queued = Mock()
    monkeypatch.setattr("apps.integrations.notification_ingress.recover", lambda: None)
    monkeypatch.setattr("apps.integrations.notification_media.cleanup_grants", lambda: None)
    monkeypatch.setattr("apps.integrations.notification_tasks.deliver_envelope.delay", queued)
    sweep_notification_outbox()
    queued.assert_called_once_with(later.envelope_id)


@pytest.mark.parametrize("state,expected", [("retrying", "held"), ("accepted", "accepted")])
def test_processed_envelope_still_recovers_expired_accepted_leg(monkeypatch, state, expected):
    from apps.integrations.notification_tasks import deliver_envelope
    row = delivery(space(), account(), state=state, claim_until=timezone.now() - timedelta(minutes=1))
    row.envelope.source_kind, row.envelope.processed_at = "fm.test", timezone.now()
    row.envelope.save(update_fields=["source_kind", "processed_at"])
    monkeypatch.setattr("apps.integrations.notification_outbox.ready", lambda _: True)
    monkeypatch.setattr("apps.integrations.notification_delivery.ensure_deliveries", lambda _: None)
    monkeypatch.setattr("apps.integrations.notification_delivery.fallback_if_exhausted", lambda _: None)
    monkeypatch.setattr("apps.integrations.notification_delivery.send", claim)
    deliver_envelope(row.envelope_id)
    row.refresh_from_db()
    assert row.state == expected and row.claim_until is None


def proof_case(monkeypatch):
    monkeypatch.setattr("apps.integrations.recipients_owners.eligible_owner", lambda *args: True)
    monkeypatch.setattr("apps.integrations.dispatch_channels.channel_module_blocks", lambda *args: False)
    monkeypatch.setattr("apps.makerspaces.servability.is_servable", lambda *args, **kwargs: True)
    tenant, user, now = space(), account(), timezone.now()
    config = ChannelConfiguration.objects.create(makerspace=tenant, channel="whatsapp", provider="meta",
        sender_key="meta:234:345", integration_identity="345", enabled=True, personal_enabled=True)
    challenge = NotificationEndpointChallenge.objects.create(makerspace=tenant, user=user,
        configuration=config, integration_generation=1, integration_identity="345", code_digest=digest("x" * 43),
        consented_at=now - timedelta(minutes=5), expires_at=now + timedelta(minutes=5), consent_version="v1")
    NotificationEndpointChallenge.objects.filter(pk=challenge.pk).update(created_at=now - timedelta(minutes=5))
    return config, user, challenge, now


@pytest.mark.parametrize("source", ["member_settings", "native_app", "account_archive", "inbound_stop"])
def test_queued_proof_cannot_override_newer_withdrawal(monkeypatch, source):
    config, user, challenge, now = proof_case(monkeypatch)
    withdrawal = MessagingConsent.objects.create(makerspace=config.makerspace, user=user, channel="whatsapp",
        action="opted_out", source=source)
    with proof_receipt(now - timedelta(minutes=4)), pytest.raises(ValidationError):
        consume(config, EndpointProof("x" * 43, "+14155550123", "345", "+14155550123", private=True))
    assert not NotificationEndpoint.objects.exists()
    assert list(MessagingConsent.objects.values_list("pk", flat=True)) == [withdrawal.pk]
    challenge.refresh_from_db()
    assert challenge.attempts == 1 and challenge.consumed_at is None


def test_new_signed_proof_after_withdrawal_can_connect(monkeypatch):
    config, user, _, _ = proof_case(monkeypatch)
    MessagingConsent.objects.create(makerspace=config.makerspace, user=user, channel="whatsapp",
        action="opted_out", source="member_settings")
    endpoint = consume(config, EndpointProof("x" * 43, "+14155550123", "345", "+14155550123", private=True))
    assert endpoint.verification_state == "verified"
    assert MessagingConsent.objects.order_by("-pk").first().action == "opted_in"


@pytest.mark.parametrize("provider_timestamp", [None, "original"])
@pytest.mark.parametrize("transport", ["canonical", "legacy"])
def test_replayed_stop_keeps_newer_connection(receipt_only_cutover, provider_timestamp, transport):
    tenant, user, now = space(), account(), timezone.now()
    config = ChannelConfiguration.objects.create(makerspace=tenant, channel="whatsapp", provider="meta",
        sender_key="meta:234:345", integration_identity="345")
    from django.utils.crypto import salted_hmac
    identity = salted_hmac("notification.endpoint.identity.v1",
        f"{config.pk}:1:+14155550123", algorithm="sha256").hexdigest()
    event = CallbackEvent(identity_digest=identity, opt_out=True,
        provider_timestamp=str(int((now - timedelta(days=1)).timestamp())) if provider_timestamp else None)
    protection = {"stop": True, "phone_hash": recipient_hash("phone", "+14155550123"),
        "timestamp": event.provider_timestamp}
    receipt = (accept_callback(config, event, identity="old-stop", protection=protection) if transport == "canonical"
        else accept_legacy(channel="whatsapp", provider="meta", makerspace_id=tenant.pk,
            sender_key=config.sender_key, kind="inbound", dedupe_id="old-stop",
            payload={**protection, "destination": "+14155550123"}))
    # Reconnection occurs after protection committed, before gated tenant replay.
    endpoint = NotificationEndpoint.objects.create(makerspace=tenant, user=user, configuration=config,
        channel="whatsapp", provider="meta", destination="+14155550123", provider_subject="+14155550123",
        identity_digest=identity, integration_identity="345", integration_generation=1,
        verified_at=timezone.now(), consented_at=timezone.now(), consent_version="v1")
    MessagingSuppression.objects.update(lifted_at=timezone.now())
    receipt_only_cutover.route = "canonical"
    receipt_only_cutover.save(update_fields=["route"])
    assert process(receipt.pk)
    endpoint.refresh_from_db()
    assert endpoint.revoked_at is None
    assert not MessagingSuppression.objects.filter(lifted_at=None).exists()


@pytest.mark.parametrize("mismatch", [None, "sender", "generation", "attempt", "target", "ambiguous", "provider", "tenant"])
def test_purged_target_receipt_finishes_only_for_exact_reference(receipt_only_cutover, mismatch):
    tenant, user = space(), account()
    config = ChannelConfiguration.objects.create(makerspace=tenant, channel="whatsapp", provider="meta",
        integration_identity="345", sender_key="meta:234:345", generation=2)
    row = delivery(tenant, user, channel="whatsapp", state="accepted", integration_identity="345",
        integration_generation=2, sender_key=config.sender_key, provider_id="wamid.retired", attempt_count=1)
    row.provider = "meta"
    row.save(update_fields=["provider"])
    remember(row)
    receipt = accept_callback(config, CallbackEvent(provider_id=row.provider_id, state="delivered",
        delivery_id=row.pk, delivery_attempt=1), identity="retired-status")
    row.delete()
    ref = NotificationProviderReference.objects.get()
    fields = {"sender": ("sender_key", "wrong"), "generation": ("generation", 3),
        "attempt": ("attempt", 2), "target": ("delivery_reference", 987654), "ambiguous": ("ambiguous", True),
        "provider": ("provider", "twilio"), "tenant": ("makerspace_reference", tenant.pk + 1)}
    if mismatch:
        field, value = fields[mismatch]
        setattr(ref, field, value)
        ref.save(update_fields=[field])
    receipt_only_cutover.route = "canonical"
    receipt_only_cutover.save(update_fields=["route"])
    assert process(receipt.pk) is (mismatch is None)
    receipt.refresh_from_db()
    assert receipt.protection_applied
    assert receipt.state == ("processed" if mismatch is None else "held")
    assert not NotificationDelivery.objects.exists()


@pytest.mark.parametrize("state", ["sent", "delivered", "read", "failed"])
@pytest.mark.parametrize("stamp", [None, "invalid", "original"])
def test_provider_times_are_not_replay_times(state, stamp):
    tenant, now = space(), timezone.now()
    row = delivery(tenant, account(), state="accepted", provider_id="SM1", sender_key="sender")
    config = SimpleNamespace(makerspace=tenant, channel="sms", provider="twilio", generation=0,
        integration_identity="", sender_key="sender")
    old = (now - timedelta(days=4)).replace(microsecond=0)
    value = str(int(old.timestamp())) if stamp == "original" else stamp
    apply_callback(config, CallbackEvent(provider_id="SM1", state=state), observation={"timestamp": value})
    row.refresh_from_db()
    assert getattr(row, state + "_at") == (old if stamp == "original" else None)
    assert row.updated_at >= now
    # An identical later replay cannot replace an original provider fact.
    apply_callback(config, CallbackEvent(provider_id="SM1", state=state), observation={"timestamp": value})
    row.refresh_from_db()
    assert getattr(row, state + "_at") == (old if stamp == "original" else None)
