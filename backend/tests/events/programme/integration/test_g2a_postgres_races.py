"""Actual PostgreSQL locks: fence-before-Event, RSVP seats and erasure races."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier, Event as Signal

import pytest
from django.db import close_old_connections, connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.encryption.account_models import PiiAccountWriteFence
from apps.encryption.account_write_fence import ACCOUNT_LOCK_NAMESPACE
from apps.encryption.models import PiiMakerspaceWriteFence
from apps.encryption.write_fence import (
    GLOBAL_LOCK_NAMESPACE, TENANT_LOCK_NAMESPACE, PiiWriteFenced, close_makerspace,
)
from apps.events import services_write_boundary
from apps.events.hackathons.admission_errors import ProgrammeError
from apps.events.hackathons.admission_rsvp import rsvp
from apps.events.models import Event, EventRegistration
from apps.events.services_event_details import update_event
from apps.payments.models import Payment
from .g2a_support import canonical_world, apply, command

pytestmark = pytest.mark.django_db(transaction=True)


def observe_fence(monkeypatch):
    entered = Signal()
    real = services_write_boundary.fences

    @contextmanager
    def observe(**kwargs):
        entered.set()
        with real(**kwargs):
            yield
    monkeypatch.setattr(services_write_boundary, "fences", observe)
    return entered


def edit_in_worker(world):
    close_old_connections()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '8s'")
        from datetime import timedelta
        return update_event(world.event, actor=world.manager, title="Must not commit",
                            starts_at=world.event.starts_at + timedelta(minutes=1))
    finally:
        close_old_connections()


def test_tenant_fence_blocks_before_any_event_lock(canonical_world, monkeypatch):
    w = canonical_world
    entered = observe_fence(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock_shared(%s, 0)", [GLOBAL_LOCK_NAMESPACE])
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [TENANT_LOCK_NAMESPACE, w.space.pk])
            future = pool.submit(edit_in_worker, w)
            assert entered.wait(5)
            Event.objects.select_for_update(nowait=True).get(pk=w.event.pk)
            close_makerspace(w.space.pk, PiiMakerspaceWriteFence.OperationKind.DECRYPT_ROLLBACK, w.manager.pk)
        with pytest.raises(PiiWriteFenced):
            future.result(timeout=12)
    w.event.refresh_from_db()
    assert w.event.title == "Workshop"


def test_owner_erasure_fence_blocks_date_writer_before_event(canonical_world, monkeypatch):
    w = canonical_world
    apply(w)
    entered = observe_fence(monkeypatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s, %s)", [ACCOUNT_LOCK_NAMESPACE, w.owner.pk])
            future = pool.submit(edit_in_worker, w)
            assert entered.wait(5)
            Event.objects.select_for_update(nowait=True).get(pk=w.event.pk)
            PiiAccountWriteFence.objects.create(user=w.owner, state="closed", epoch=2)
        with pytest.raises(PiiWriteFenced):
            future.result(timeout=12)
    w.event.refresh_from_db()
    assert w.event.title == "Workshop"


def test_two_real_rsvps_compete_for_one_hard_seat(canonical_world):
    w = canonical_world
    first, second = apply(w), apply(w, w.other)
    barrier = Barrier(2)

    def respond(actor, app):
        close_old_connections()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '10s'")
            barrier.wait(8)
            try:
                rsvp(event_id=w.event.pk, actor=actor, data=command(app.version, decision="accept"))
                return "confirmed"
            except ProgrammeError as exc:
                return exc.detail["code"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        tasks = [pool.submit(respond, w.owner, first), pool.submit(respond, w.other, second)]
        assert sorted(task.result(timeout=20) for task in tasks) == ["capacity_full", "confirmed"]
    assert EventRegistration.objects.filter(event=w.event, status="registered").count() == 1
    assert Payment.objects.filter(makerspace=w.space, subject_type="event_registration").count() == 1


def test_application_and_rsvp_never_lock_user_or_account_key_rows(canonical_world):
    w = canonical_world
    with CaptureQueriesContext(connection) as captured:
        app = apply(w)
        rsvp(event_id=w.event.pk, actor=w.owner, data=command(app.version, decision="accept"))
    forbidden = [row["sql"] for row in captured if "FOR UPDATE" in row["sql"].upper()
                 or "FOR NO KEY UPDATE" in row["sql"].upper()]
    assert not any('"accounts_user"' in sql or '"encryption_accountpiikey"' in sql for sql in forbidden)


def test_source_freeze_refuses_before_domain_mutation(canonical_world):
    from apps.tenant_migration.gate_errors import SourceMigrationGateClosed
    from tests.tenant_migration.source_gate_helpers import close_gate
    w = canonical_world
    close_gate(w.space, w.manager)
    with pytest.raises(SourceMigrationGateClosed):
        update_event(w.event, actor=w.manager, title="Frozen")
    w.event.refresh_from_db()
    assert w.event.title == "Workshop" and w.event.version == 1


def test_date_edit_wins_against_an_already_prepared_application(canonical_world, monkeypatch):
    from datetime import timedelta
    from .g2a_support import BasicForms
    w = canonical_world
    prepared, resume = Signal(), Signal()
    original = BasicForms.prepare

    def pause_preparation(self, **kwargs):
        result = original(self, **kwargs)
        prepared.set()
        assert resume.wait(8)
        return result
    monkeypatch.setattr(BasicForms, "prepare", pause_preparation)

    def submit():
        close_old_connections()
        try:
            return apply(w)
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(submit)
        try:
            assert prepared.wait(5)
            update_event(w.event, actor=w.manager, starts_at=w.event.starts_at + timedelta(minutes=1))
        finally:
            resume.set()
        with pytest.raises(ProgrammeError) as error:
            future.result(timeout=12)
    assert error.value.detail["code"] == "event_date_changed"
    assert not EventRegistration.objects.filter(event=w.event).exists()
    assert not Payment.objects.filter(makerspace=w.space).exists()


def test_event_cancellation_racing_rsvp_never_leaves_live_admission(canonical_world):
    from apps.events.services_lifecycle import cancel
    from apps.events.credentials.models import EventRegistrationCredential
    w = canonical_world
    app = apply(w)
    barrier = Barrier(2)

    def race(action):
        close_old_connections()
        try:
            barrier.wait(8)
            if action == "cancel":
                cancel(w.event, actor=w.manager)
                return "cancelled"
            try:
                rsvp(event_id=w.event.pk, actor=w.owner, data=command(app.version, decision="accept"))
                return "confirmed"
            except ProgrammeError as exc:
                return exc.detail["code"]
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(race, action) for action in ("cancel", "rsvp")]
        results = [future.result(timeout=20) for future in futures]
    assert "cancelled" in results
    app.refresh_from_db()
    assert app.state == "withdrawn" and app.registration.status == "cancelled"
    assert not EventRegistrationCredential.objects.filter(registration_id=app.registration_id, revoked_at=None).exists()
