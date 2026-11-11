"""Canonical addressed retention: every boundary that must keep or may delete a row."""
from contextlib import contextmanager
from datetime import timedelta
from itertools import count
from unittest.mock import patch

import pytest
from django.conf import settings
from django.utils import timezone

from apps.integrations.models_contract import NotificationDelivery, NotificationEnvelope
from apps.integrations.models_cutover import (
    NotificationCutover, NotificationIngress, NotificationLegacyMapping, NotificationProviderReference,
)
from apps.integrations.models_messaging_consent import MessagingRecipientCorrelation
from apps.integrations.notification_retention import run_canonical_retention
from .reconciliation_helpers import account, delivery, space

pytestmark = pytest.mark.django_db
SENDER = "twilio:AC:retention"
_numbers = count(1)


@pytest.fixture
def tenant():
    return space("retention")


@pytest.fixture
def user():
    return account("retention-member")


def leg(tenant, user, *, age, processed=True, **fields):
    fields.setdefault("sender_key", SENDER)
    row = delivery(tenant, user, number=next(_numbers), **fields)
    NotificationDelivery.objects.filter(pk=row.pk).update(created_at=timezone.now() - timedelta(days=age))
    if processed:
        NotificationEnvelope.objects.filter(pk=row.envelope_id).update(processed_at=timezone.now())
    return row


def receipt(*, state="processed", age=31, protection_applied=True, sender_key=SENDER):
    processed_at = timezone.now() - timedelta(days=age) if state == "processed" else None
    return NotificationIngress.objects.create(channel="sms", provider="twilio", transport="canonical",
        sender_key=sender_key, dedupe_key=f"retention-{next(_numbers)}", payload="fernet:opaque",
        state=state, processed_at=processed_at, protection_applied=protection_applied)


def exists(row):
    return type(row).objects.filter(pk=row.pk).exists()


def unverified():
    NotificationCutover.objects.filter(pk=1).update(reconciled_at=None)


@pytest.mark.parametrize("state", ["accepted", "sent", "delivered", "read", "skipped"])
def test_terminal_success_and_skip_expire_after_ninety_days(tenant, user, state):
    old, young = leg(tenant, user, state=state, age=91), leg(tenant, user, state=state, age=89)
    assert run_canonical_retention()["deleted"] == 1
    assert not exists(old) and exists(young)
    # Intent rows are not delivery history and keep their dedupe identity.
    assert NotificationEnvelope.objects.filter(pk=old.envelope_id).exists()


def test_failed_legs_keep_a_year_unless_delivery_evidence_wins(tenant, user):
    kept = leg(tenant, user, state="failed", age=364)
    expired = leg(tenant, user, state="failed", age=366)
    evidenced = leg(tenant, user, state="failed", age=91, delivered_at=timezone.now())
    run_canonical_retention()
    assert exists(kept) and not exists(expired) and not exists(evidenced)


@pytest.mark.parametrize("fields", [
    {"state": "retrying"},
    {"state": "held"},
    {"state": "failed", "retryable": True},
    {"state": "accepted", "claim_until": timezone.now()},
], ids=["retrying", "held", "retryable", "leased"])
def test_in_flight_held_or_leased_legs_are_never_deleted(tenant, user, fields):
    row = leg(tenant, user, age=1000, **fields)
    run_canonical_retention()
    assert exists(row)


def test_legs_of_an_unprocessed_envelope_are_kept(tenant, user):
    row = leg(tenant, user, state="skipped", age=1000, processed=False)
    run_canonical_retention()
    assert exists(row)


def test_provider_leg_needs_its_exact_permanent_reference(tenant, user):
    missing = leg(tenant, user, state="delivered", age=91, provider_id="SM-missing")
    ambiguous = leg(tenant, user, state="delivered", age=91, provider_id="SM-ambiguous")
    referenced = leg(tenant, user, state="delivered", age=91, provider_id="SM-ok")
    for row, flag in ((ambiguous, True), (referenced, False)):
        NotificationProviderReference.objects.create(provider="twilio", sender_key=SENDER,
            provider_id=row.provider_id, delivery_reference=row.pk, makerspace_reference=tenant.pk,
            ambiguous=flag)
    run_canonical_retention()
    assert exists(missing) and exists(ambiguous) and not exists(referenced)
    # The reference that settles late callbacks for the deleted leg survives.
    assert NotificationProviderReference.objects.filter(delivery_reference=referenced.pk).exists()


@pytest.mark.parametrize("state", ["pending", "held"])
def test_unprocessed_receipt_on_the_sender_blocks_its_legs(tenant, user, state):
    blocked = leg(tenant, user, state="delivered", age=91)
    other = leg(tenant, user, state="delivered", age=91, sender_key="twilio:AC:other")
    receipt(state=state)
    run_canonical_retention()
    assert exists(blocked) and not exists(other)


def test_probing_correlation_barrier_keeps_its_probe(tenant, user):
    probe = leg(tenant, user, channel="whatsapp", state="accepted", age=91)
    settled = leg(tenant, user, channel="whatsapp", state="accepted", age=91)
    MessagingRecipientCorrelation.objects.create(sender_key=SENDER, phone_hash="p1",
        state="probing", probe_notification_delivery=probe)
    confirmed = MessagingRecipientCorrelation.objects.create(sender_key=SENDER, phone_hash="p2",
        state="confirmed", probe_notification_delivery=settled)
    run_canonical_retention()
    assert exists(probe) and not exists(settled)
    confirmed.refresh_from_db()
    assert confirmed.state == "confirmed" and confirmed.probe_notification_delivery_id is None


def test_unverified_legacy_mappings_keep_their_canonical_targets(tenant, user):
    mapped = leg(tenant, user, state="delivered", age=400, historical=True)
    mapped_receipt = receipt(age=400)
    for canonical, model in ((mapped, "NotificationDelivery"), (mapped_receipt, "NotificationIngress")):
        NotificationLegacyMapping.objects.create(legacy_model="Legacy" + model, legacy_id=canonical.pk,
            canonical_model=model, canonical_id=canonical.pk, makerspace=tenant, disposition="history")
    unverified()
    run_canonical_retention()
    assert exists(mapped) and exists(mapped_receipt)
    NotificationCutover.objects.filter(pk=1).update(reconciled_at=timezone.now())
    run_canonical_retention()
    assert not exists(mapped) and not exists(mapped_receipt)
    assert NotificationLegacyMapping.objects.count() == 2


def test_receipts_expire_thirty_days_after_processing_only(tenant):
    old, young = receipt(age=31), receipt(age=29)
    pending, held = receipt(state="pending"), receipt(state="held")
    unprotected = receipt(age=400, protection_applied=False)
    NotificationIngress.objects.filter(pk__in=[pending.pk, held.pk]).update(
        received_at=timezone.now() - timedelta(days=400))
    assert run_canonical_retention()["receipts"] == 1
    assert not exists(old)
    assert all(exists(row) for row in (young, pending, held, unprotected))


def test_frozen_tenant_is_counted_and_untouched(tenant, user):
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    row = leg(tenant, user, state="delivered", age=91)

    @contextmanager
    def frozen(space_id):
        raise SourceMigrationGateClosed("frozen")
        yield

    with patch("apps.tenant_migration.gate_runtime.boundary_tenant_write", frozen):
        counts = run_canonical_retention()
    assert exists(row) and counts["skipped"] >= 1 and counts["deleted"] == 0


def test_push_legs_follow_their_device_children(tenant, user):
    from apps.accounts.models import DeviceGrant, NativeAppRegistration
    from apps.integrations.models import PushDevice
    from apps.notifications.models_push import MemberPushDelivery
    now = timezone.now()
    registration = NativeAppRegistration.objects.create(app_id="test.retention", platform="apple",
        environment="development", verifier_config_key="test", status=NativeAppRegistration.Status.APPROVED)
    grant = DeviceGrant.objects.create(registration=registration, user=user, platform="apple",
        app_id="test.retention", signing_identity="test", environment="development",
        attestation_subject_fingerprint="a" * 64, attested_at=now, last_used_at=now)
    device = PushDevice.objects.create(user=user, makerspace=tenant, device_grant=grant, provider="apns",
        environment="development", token_ciphertext="secret", token_fingerprint="b" * 64, active=True)

    def push(child_status, age):
        parent = leg(tenant, user, channel="native_push", state="sent", age=age, sender_key="")
        MemberPushDelivery.objects.create(envelope_delivery=parent, push_device=device, status=child_status)
        return parent

    active, sent = push("pending", 1000), push("sent", 91)
    failed_young, failed_old = push("failed", 91), push("failed", 366)
    run_canonical_retention()
    assert exists(active) and exists(failed_young)
    assert not exists(sent) and not exists(failed_old)
    assert set(MemberPushDelivery.objects.values_list("status", flat=True)) == {"pending", "failed"}


def test_registered_in_both_schedulers_and_the_fanout_gate():
    from apps.operations.management.commands.run_scheduled_tasks import SCHEDULED_TASKS
    from apps.tenant_migration.gate_policy_tasks import FANOUT_GATE_PARTICIPANTS, TASK_INTERNAL_PARTICIPANTS
    task = "apps.integrations.tasks_messaging.canonical_retention_task"
    assert settings.CELERY_BEAT_SCHEDULE["canonical-messaging-retention"]["task"] == task
    assert ("canonical-messaging-retention", task, 60) in SCHEDULED_TASKS
    assert task in TASK_INTERNAL_PARTICIPANTS
    assert "apps.integrations.notification_retention.run_canonical_retention" in FANOUT_GATE_PARTICIPANTS
