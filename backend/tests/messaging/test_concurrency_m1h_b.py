"""Real separate PostgreSQL connections, not mocked select_for_update calls.

The canonical WhatsApp probe barrier serializes on ``lock_whatsapp_sender`` before
any row lock: unmapped STOP, probe confirmation and probe claims (D1).
"""
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from django.db import close_old_connections, connection, transaction

from apps.integrations.messaging.correlation import confirm_canonical_probe
from apps.integrations.messaging.locks import lock_whatsapp_sender
from apps.integrations.messaging.protections import recipient_hash
from apps.integrations.messaging.stops import process_stop
from apps.integrations.models import MessagingRecipientCorrelation
from apps.integrations.notification_addressed import prepare_whatsapp
from tests.messaging.test_barrier_m1h_b import SENDER, wa_leg


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("first_operation", ["stop", "confirm"])
def test_sender_serialization_orders_unmapped_stop_and_probe_confirmation(space, member, first_operation):
    assert connection.vendor == "postgresql"
    probe = wa_leg(space, member, "probe")
    assert prepare_whatsapp(probe) is True
    held, second_started, release = threading.Event(), threading.Event(), threading.Event()
    second_acquired = threading.Event()
    operations = {
        "stop": lambda: process_stop(SimpleNamespace(channel="whatsapp", sender_key=SENDER,
            payload={"stop": True, "alias_hash": recipient_hash("alias", "unknown")})),
        "confirm": lambda: confirm_canonical_probe(probe, phone_hash=recipient_hash("phone", member.phone_e164)),
    }

    def run(operation, owns_first_lock):
        close_old_connections()
        try:
            with transaction.atomic():
                if owns_first_lock:
                    lock_whatsapp_sender(SENDER)
                    held.set()
                    assert release.wait(10)
                else:
                    assert held.wait(10)
                    second_started.set()
                    lock_whatsapp_sender(SENDER)
                    second_acquired.set()
                operations[operation]()
        finally:
            close_old_connections()

    other = "confirm" if first_operation == "stop" else "stop"
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(run, first_operation, True)
        assert held.wait(10)
        b = pool.submit(run, other, False)
        assert second_started.wait(10)
        assert not second_acquired.wait(0.2)
        release.set()
        a.result(timeout=20)
        b.result(timeout=20)
    correlation = MessagingRecipientCorrelation.objects.get()
    # STOP first leaves the probe closed; confirmation first is subsequently blocked.
    assert correlation.state == "blocked"
    after = wa_leg(space, member, "after-race")
    assert prepare_whatsapp(after) is False
    after.refresh_from_db()
    assert (after.state, after.last_error) == ("skipped", "identity_unconfirmed")


@pytest.mark.django_db(transaction=True)
def test_two_tenants_cannot_submit_two_platform_probes_concurrently(space, member):
    from apps.makerspaces.models import Makerspace
    from tests.fixed_roles.helpers import assign_builtin_roles

    other = Makerspace.objects.create(name="Concurrent sender tenant", slug="concurrent-sender-tenant")
    assign_builtin_roles(member, other, "member")
    rows = [wa_leg(space, member, "first"), wa_leg(other, member, "second")]
    ready = threading.Barrier(2)

    def run(row):
        close_old_connections()
        try:
            ready.wait(timeout=10)
            return prepare_whatsapp(row)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, rows))
    assert sorted(results) == [False, True]
    assert MessagingRecipientCorrelation.objects.count() == 1
