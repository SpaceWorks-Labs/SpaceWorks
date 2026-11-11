"""A queued migration must drain delivery, never block its inner transactions."""
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

import pytest
from django.db import close_old_connections, connection, transaction

from apps.integrations.messaging import worker
from apps.integrations.messaging.transport import SendResult
from apps.tenant_migration.gate_locks import SOURCE_GATE_LOCK_NAMESPACE, acquire_exclusive
from tests.messaging.helpers_m1h_b import setup_pipeline


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("phase", ["prepare", "complete"])
@pytest.mark.parametrize("channel", ["sms", "whatsapp"])
def test_delivery_finishes_while_migration_exclusive_is_queued(space, member, phase, channel):
    pipeline = setup_pipeline(space, member)
    row = pipeline.enqueue(channel=channel)
    started, acquired = Event(), Event()
    backend = []

    def freeze():
        close_old_connections()
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SET LOCAL lock_timeout = '5s'")
                cursor.execute("SELECT pg_backend_pid()")
                backend.append(cursor.fetchone()[0])
                started.set()
                acquire_exclusive(space.pk)
                acquired.set()
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = None

        def queue_freeze():
            nonlocal future
            future = pool.submit(freeze)
            assert started.wait(5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                with connection.cursor() as cursor:
                    cursor.execute("""SELECT EXISTS (SELECT 1 FROM pg_locks
                        WHERE pid=%s AND locktype='advisory' AND classid=%s
                        AND objid=%s AND NOT granted)""",
                        [backend[0], SOURCE_GATE_LOCK_NAMESPACE, space.pk])
                    if cursor.fetchone()[0]:
                        return
                time.sleep(0.01)
            pytest.fail("Migration never queued behind the delivery boundary")

        prepare = worker._prepare

        def preparing(pk):
            if phase == "prepare":
                queue_freeze()
            return prepare(pk)

        def send(*args, **kwargs):
            assert not connection.in_atomic_block
            if phase == "complete":
                queue_freeze()
            assert not acquired.is_set()
            return SendResult(message_id="provider-accepted")

        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '1s'")
            with patch.object(worker, "_prepare", side_effect=preparing), patch.object(worker, "send_message", side_effect=send):
                worker.deliver(row.pk)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = DEFAULT")
        assert future is not None
        future.result(timeout=10)
    assert acquired.is_set()
    row.refresh_from_db()
    assert row.status == "accepted" and row.provider_message_id == "provider-accepted"


@pytest.mark.django_db
@pytest.mark.parametrize("operation", ["consent", "callback", "recovery", "stop_annotation"])
def test_tenant_mutations_take_gate_before_whatsapp_sender(space, member, operation):
    from datetime import timedelta
    from django.utils import timezone
    from apps.integrations.messaging import consent, stops, sweep, webhook_processing
    from apps.integrations.messaging.protections import recipient_hash
    from apps.integrations.models import MessagingWebhookEvent
    from apps.tenant_migration import gate_runtime

    pipeline = setup_pipeline(space, member)
    row = pipeline.enqueue(channel="whatsapp")
    worker._prepare(row.pk)
    event = MessagingWebhookEvent.objects.create(provider="meta", channel="whatsapp", sender_key=pipeline.wa.sender_key,
        dedupe_id="lock-order", kind="inbound", payload={"stop": True, "phone_hash": recipient_hash("phone", member.phone_e164)})
    checks = []
    validate = gate_runtime._assert_gate_state
    module = {"consent": consent, "callback": webhook_processing, "recovery": sweep, "stop_annotation": stops}[operation]
    sender_lock = module.lock_whatsapp_sender

    def gate(pk):
        validate(pk)
        checks.append("gate")

    def sender(key):
        assert "gate" in checks
        checks.append("sender")
        sender_lock(key)

    with patch.object(gate_runtime, "_assert_gate_state", side_effect=gate), patch.object(module, "lock_whatsapp_sender", side_effect=sender):
        if operation == "consent":
            consent.grant_consent(user=member, makerspace_id=space.pk, channel="whatsapp", action="opted_in")
        elif operation == "callback":
            webhook_processing.accept_event(provider="meta", channel="whatsapp", sender_key=pipeline.wa.sender_key,
                dedupe_id="lock-order-status", kind="status", payload={"message_id": "wamid.order",
                    "delivery_id": str(row.pk), "status": "sent", "alias_hash": "known-alias"})
        elif operation == "recovery":
            sweep._recover(row.pk, timezone.now() + timedelta(minutes=2))
        else:
            stops.annotate_stop(event.pk)
    assert "sender" in checks
