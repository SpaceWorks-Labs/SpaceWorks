"""Real PostgreSQL preparation and affected-owner regressions (EV2-B)."""
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue

import pytest
from django.db import connection, connections, transaction

from apps.encryption.account_write_fence import account_fences, assert_account_fence_held
from apps.events.certificates.issuance import create_for_subject_locked
from apps.events.certificates.preparation import prepare_issuance
from apps.events.credentials.boundary import event_command
from apps.events.credentials.errors import ProgrammeConflict
from apps.events.credentials.scopes import registrations
from apps.events.models_event import Event
from apps.events.models_registration import EventRegistration
from tests.encryption.conftest import enabled_encryption
from tests.events.checkin_helpers import make_event, make_member, make_space, register

pytestmark = pytest.mark.django_db(transaction=True)


def test_certificate_insert_never_decrypts_or_provisions_a_key_under_event_lock(monkeypatch):
    space = make_space("g2b-encrypted-cert")
    event, member = make_event(space), make_member(space)
    with enabled_encryption():
        registration = register(event, member, status="attended")
        prepared = prepare_issuance(event.pk, [{"subject_kind": "registration", "subject_id": registration.pk}])
        with event_command(event.pk, account_ids=prepared.account_ids, revalidate=prepared.revalidate) as (event, _):
            def forbidden(*args, **kwargs):
                pytest.fail("Broker/decryption called under Event lock")
            with monkeypatch.context() as patch:
                patch.setattr("apps.encryption.mappers.get_or_create_active_dek", forbidden)
                patch.setattr("apps.encryption.mappers.get_dek", forbidden)
                patch.setattr("apps.encryption.services.unwrap_dek", forbidden)
                row = create_for_subject_locked(event, subject_kind="registration",
                    subject_id=registration.pk, prepared=prepared)
        with connection.cursor() as cursor:
            cursor.execute("SELECT recipient_name FROM events_eventattendancecertificate WHERE id=%s", [row.pk])
            assert cursor.fetchone()[0].startswith("pii:gcm:")


def test_preparation_refuses_scope_or_name_changed_before_event_lock():
    space = make_space("g2b-preparation-race")
    event, member = make_event(space), make_member(space)
    registration = register(event, member, status="attended")
    prepared = prepare_issuance(event.pk, [{"subject_kind": "registration", "subject_id": registration.pk}])
    registration.name = "Changed recipient"
    registration.save(update_fields=("name",))
    with pytest.raises(ProgrammeConflict):
        with event_command(event.pk, account_ids=prepared.account_ids, revalidate=prepared.revalidate):
            pytest.fail("Stale prepared source entered the command")


def test_all_affected_accounts_are_fenced_before_the_event_row():
    space = make_space("g2b-blocking-order")
    event, member = make_event(space), make_member(space)
    registration = register(event, member)
    scope = registrations(event.pk, [registration.pk])
    pids = Queue()

    def command():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pids.put(cursor.fetchone()[0])
            with event_command(event.pk, account_ids=scope.account_ids, revalidate=scope.revalidate):
                assert_account_fence_held(member.pk)
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(), account_fences([member.pk], [space.pk], exclusive=True):
            future = pool.submit(command)
            pid = pids.get(timeout=5)
            deadline = time.monotonic() + 5
            while True:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT wait_event FROM pg_stat_activity WHERE pid=%s", [pid])
                    waiting = cursor.fetchone()
                if waiting and waiting[0] == "advisory":
                    break
                assert time.monotonic() < deadline, "Writer never waited for the affected account fence"
                time.sleep(.02)
            # If the worker locked Event first this NOWAIT would fail.
            Event.objects.select_for_update(nowait=True).get(pk=event.pk)
        future.result(timeout=10)


def test_changed_owner_cannot_expand_a_predeclared_scope():
    space = make_space("g2b-owner-scope")
    event, first = make_event(space), make_member(space)
    second = make_member(space, "second")
    registration = register(event, first)
    scope = registrations(event.pk, [registration.pk])
    EventRegistration.objects.filter(pk=registration.pk).update(member=second)
    with pytest.raises(ProgrammeConflict):
        with event_command(event.pk, account_ids=scope.account_ids, revalidate=scope.revalidate):
            pytest.fail("Changed ownership was accepted")
