"""CX12: batch preparation precedes locks without changing decision atomicity."""
import base64
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from contextlib import contextmanager, nullcontext
from threading import Event as Signal
from time import monotonic, sleep

import pytest
from django.db import close_old_connections, connection, transaction, connections
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.events import services_registration_state as state
from apps.events.credentials import preparation
from apps.events.credentials.models import EventCredentialCommand, EventRegistrationCredential
from apps.events.models import EventCollaborator, EventRegistration
from apps.integrations.models_contract import NotificationDelivery
from apps.payments.models import Payment
from tests.completeness.test_bulk_lookup_contract import _snapshot, _space
from tests.events.ticketing_helpers import open_event
from tests.fixed_roles.helpers import assign_builtin_roles, staff_account
from tests.return_helpers import authenticated_client

pytestmark = [pytest.mark.django_db, pytest.mark.area_events]
DECISIONS = [("approve", "registered", "event.registration_approved"),
             ("reject", "rejected", "event.registration_rejected")]


@pytest.fixture(autouse=True)
def credential_keys(settings):
    settings.EVENT_REGISTRATION_CREDENTIAL_KEY_VERSION = 1
    settings.EVENT_REGISTRATION_CREDENTIAL_KEYS = {"1": base64.b64encode(b"e" * 32).decode()}
    settings.EVENT_REGISTRATION_CREDENTIAL_DIGEST_KEY = base64.b64encode(b"d" * 32).decode()


def _batch(*, same_event=False):
    space = _space("bulk-prepared-events")
    actor = staff_account(space, "bulk-event-manager", "space_manager")
    rows = []
    for number in range(2):
        member = User.objects.create_user(f"bulk-attendee-{number}",
            email=f"attendee-{number}@example.test", access_status="active")
        event = rows[0].event if same_event and rows else open_event(space, registration_requires_approval=True)
        rows.append(EventRegistration.objects.create(event=event, member=member, name=member.username,
            email=member.email, phone="12345678", status="pending_approval",
            custom_answers={"version": 2, "answers": {}}, credential_mode="inert"))
    return space, actor, rows, authenticated_client(actor)


def _post(client, decision, rows):
    return client.post(reverse("admin-bulk-event-registrations", args=[decision]),
        {"ids": [row.pk for row in rows]}, format="json")


def _persisted(row):
    snapshot = _snapshot(row)
    for model in (EventRegistrationCredential, EventCredentialCommand, NotificationDelivery):
        snapshot[model._meta.label] = list(model.objects.order_by("pk").values())
    return snapshot


@pytest.mark.parametrize("decision,final_status,action", DECISIONS)
@pytest.mark.parametrize("same_event", [False, True])
def test_bulk_registration_decisions_prepare_all_events_and_issue_real_credentials(
        decision, final_status, action, same_event):
    space, actor, rows, client = _batch(same_event=same_event)
    response = _post(client, decision, rows)
    assert response.status_code == 200
    assert response.json() == {"decided": 2, "ids": [row.pk for row in rows]}
    assert list(EventRegistration.objects.order_by("pk").values_list("status", flat=True)) == [final_status] * 2
    assert AuditLog.objects.filter(makerspace=space, actor=actor, action=action).count() == 2
    credentials = list(EventRegistrationCredential.objects.order_by("registration_id").values_list(
        "registration_id", "generation", "revoked_at"))
    assert credentials == ([(row.pk, 1, None) for row in rows] if decision == "approve" else [])


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("encrypted", [False, True])
def test_bulk_locks_later_event_before_overlapping_single_decision(monkeypatch, settings, encrypted):
    """Old order: B holds E2 awaiting M; A holds E1/M then awaits E2.

    Both writers finish real preparation first (including in encrypted mode).
    PostgreSQL must report B blocked by A before A may decide its second row.
    No mocked locks or timing-only assertion can hide the old database cycle.
    """
    from apps.encryption.preparation import prepare_tenants
    from apps.events import services_write_boundary as boundary
    from apps.events.programme_locks import event_scopes
    from tests.encryption.conftest import enabled_encryption

    assert connection.vendor == "postgresql"
    settings.PII_ENCRYPTION_ENABLED = False
    with enabled_encryption() if encrypted else nullcontext():
        space, actor, rows, _ = _batch()
        member = User.objects.create_user("overlapping-attendee", email="overlap@example.test", access_status="active")
        single = EventRegistration.objects.create(event=rows[1].event, member=member, name=member.username,
            email=member.email, phone="12345678", status="pending_approval",
            custom_answers={"version": 2, "answers": {}}, credential_mode="inert")
        prepared, first_done, run_single, run_batch = Signal(), Signal(), Signal(), Signal()
        pids, committed = {}, []
        approve = state.approve_registration

        def observed(registration, *, actor):
            result = approve(registration, actor=actor)
            if registration.pk == rows[0].pk:
                transaction.on_commit(lambda: committed.append(boundary._held.get()))
                first_done.set()
                assert run_batch.wait(12), "Batch was not released."
            return result

        monkeypatch.setattr(state, "approve_registration", observed)

        def worker(kind):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '8s'")
                    cursor.execute("SET statement_timeout = '15s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids[kind] = cursor.fetchone()[0]
                client = authenticated_client(User.objects.get(pk=actor.pk))
                if kind == "single":
                    tenants = event_scopes(event_id=single.event_id)[0]
                    with prepare_tenants(tenants), preparation.prepare_event_credentials([single.event_id]):
                        prepared.set()
                        assert run_single.wait(12), "Single decision was not released."
                        response = client.post(reverse("admin-event-registration-approve", args=[single.pk]),
                                               {}, format="json")
                else:
                    response = _post(client, "approve", rows)
                return response.status_code, response.json()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            single_future = pool.submit(worker, "single")
            try:
                assert prepared.wait(10), "Single writer did not prepare."
                batch_future = pool.submit(worker, "batch")
                assert first_done.wait(10), "Batch did not finish its first real decision."
                assert pids["batch"] != pids["single"]
                run_single.set()
                deadline, blockers = monotonic() + 5, []
                while monotonic() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_blocking_pids(%s)", [pids["single"]])
                        blockers = cursor.fetchone()[0]
                    if pids["batch"] in blockers:
                        break
                    sleep(0.01)
                assert blockers == [pids["batch"]], "The required real lock overlap was not reached."
            finally:
                run_single.set()
                run_batch.set()
            batch_status, batch_body = batch_future.result(timeout=25)
            single_status, single_body = single_future.result(timeout=25)

        assert batch_status == 200
        assert batch_body == {"decided": 2, "ids": [row.pk for row in rows]}
        assert single_status == 200
        assert (single_body["id"], single_body["status"]) == (single.pk, "registered")
        all_ids = [row.pk for row in rows] + [single.pk]
        assert list(EventRegistration.objects.order_by("pk").values_list("pk", "status", "credential_mode")) == [
            (pk, "registered", "v2") for pk in all_ids]
        assert list(EventRegistrationCredential.objects.order_by("registration_id").values_list(
            "registration_id", "generation", "revoked_at")) == [(pk, 1, None) for pk in all_ids]
        assert list(Payment.objects.values()) == []  # All three events seats are free.
        assert EventCredentialCommand.objects.count() == 0
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.registration_approved").count() == 3
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.credential_issued").count() == 3
        assert committed == [None]


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("encrypted", [False, True])
def test_post_commit_registration_decision_enters_fresh_transaction_and_fences(monkeypatch, settings, encrypted):
    from apps.encryption import account_write_fence
    from apps.events import programme_locks, services_write_boundary as boundary
    from tests.encryption.conftest import enabled_encryption

    assert connection.vendor == "postgresql"
    settings.PII_ENCRYPTION_ENABLED = False
    with enabled_encryption() if encrypted else nullcontext():
        space, actor, rows, _ = _batch(same_event=True)
        entries, completed, declarations = [], [], []
        original_fences, original_source = boundary.fences, boundary.boundary_tenant_write

        @contextmanager
        def observed_source(tenant_id):
            entries.append(("source", tenant_id))
            with original_source(tenant_id):
                yield

        @contextmanager
        def observed_fences(*, tenant_ids, account_ids):
            # Both entries must acquire the real fences, with no inherited ones.
            assert connection.in_atomic_block is True
            assert programme_locks._scopes.get() is None
            assert account_write_fence._held.get() is None
            with original_fences(tenant_ids=tenant_ids, account_ids=account_ids):
                entries.append(("fences", tuple(tenant_ids), tuple(account_ids)))
                for account_id in account_ids:
                    account_write_fence.assert_account_fence_held(account_id)
                yield

        def decide_second():
            assert connection.get_autocommit() is True
            assert boundary._held.get() is None
            assert programme_locks._scopes.get() is None
            assert account_write_fence._held.get() is None
            with CaptureQueriesContext(connection) as queries:
                result = state.approve_registration(rows[1], actor=actor)
            completed.append((result.pk, result.status, result.credential_mode))
            # A fresh boundary locks the Event again before its decision writes.
            assert len([query for query in queries if 'FROM "events_event"' in query["sql"]
                        and "FOR UPDATE" in query["sql"]]) == 1
            assert boundary._held.get() is None

        monkeypatch.setattr(boundary, "fences", observed_fences)
        monkeypatch.setattr(boundary, "boundary_tenant_write", observed_source)
        with boundary.write_boundary(rows[0].event, actor=actor):
            declaration = boundary._held.get()
            state.approve_registration(rows[0], actor=actor)
            assert boundary._held.get() is declaration
            declarations.append(declaration)
            transaction.on_commit(decide_second)
            assert completed == []
        accounts = tuple(sorted([actor.pk, *(row.member_id for row in rows)]))
        assert entries == [("source", space.pk), ("fences", (space.pk,), accounts)] * 2
        assert declarations[0] == ({rows[0].event_id}, ((space.pk,), accounts))
        assert completed == [(rows[1].pk, "registered", "v2")]
        assert list(EventRegistration.objects.order_by("pk").values_list("pk", "status", "credential_mode")) == [
            (row.pk, "registered", "v2") for row in rows]
        assert list(EventRegistrationCredential.objects.order_by("registration_id").values_list(
            "registration_id", "generation", "revoked_at")) == [(row.pk, 1, None) for row in rows]
        assert list(Payment.objects.values()) == []
        assert EventCredentialCommand.objects.count() == 0
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.registration_approved").count() == 2
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.credential_issued").count() == 2


@pytest.mark.parametrize("fence_kind", ["collaborator", "account"])
def test_closed_second_event_fence_blames_affected_registration_and_restores(
        django_capture_on_commit_callbacks, fence_kind, settings):
    from apps.encryption.account_models import PiiAccountWriteFence
    from apps.encryption.account_services import prepare_account_key
    from apps.encryption.account_write_fence import account_fences
    from apps.encryption.models import PiiMakerspaceWriteFence
    from apps.encryption.preparation import prepare_tenants
    from apps.encryption.services import get_or_create_active_dek
    from apps.encryption.write_fence import PiiWriteFenced
    from tests.encryption.conftest import enabled_encryption

    with enabled_encryption():
        space, actor, rows, client = _batch()
        collaborator = _space("bulk-fenced-second-event-dependency")
        EventCollaborator.objects.create(event=rows[1].event, makerspace=collaborator, status="accepted")
        for tenant in (space, collaborator):
            get_or_create_active_dek(tenant.pk)
        if fence_kind == "account":
            # Account fences are provisioned on first use of the account key service.
            settings.ACCOUNT_SAVED_DETAILS_ENABLED = True
            settings.ACCOUNT_PII_KEY_BROKER = "local"
            settings.ACCOUNT_PII_MASTER_KEY = settings.PII_MASTER_KEY
            settings.ACCOUNT_PII_MASTER_KEY_PREVIOUS = ""
            prepare_account_key(rows[1].member_id)
        fence = (PiiMakerspaceWriteFence.objects.filter(makerspace=collaborator) if fence_kind == "collaborator"
                 else PiiAccountWriteFence.objects.filter(user_id=rows[1].member_id))
        assert fence.update(state="closed", operation_id=None) == 1
        assert list(fence.values_list("state", "operation_id")) == [("closed", None)]
        before = _persisted(rows[0])
        with pytest.raises(PiiWriteFenced) as error:
            with transaction.atomic(), account_fences([rows[1].member_id], [space.pk, collaborator.pk]):
                pytest.fail("A closed dependency fence admitted a write.")
        assert type(error.value) is PiiWriteFenced
        assert str(error.value) == "Protected writes are temporarily unavailable."
        attribute = "fence_tenant_id" if fence_kind == "collaborator" else "fence_account_id"
        assert getattr(error.value, attribute) == (collaborator.pk if fence_kind == "collaborator" else rows[1].member_id)
        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            refused = _post(client, "approve", rows)
        assert refused.status_code == 409
        assert refused.json() == {"code": "bulk_failed",
            "detail": "Nothing was changed: one item could not be decided.", "failed_id": rows[1].pk,
            "cause": "Protected writes are temporarily unavailable."}
        assert _persisted(rows[0]) == before
        assert callbacks == []

        # E1 has no dependency on E2's closed fence; roll back this successful
        # probe so reopening can retry the exact original pending batch.
        with prepare_tenants([space.pk]), preparation.prepare_event_credentials([rows[0].event_id]):
            with django_capture_on_commit_callbacks(execute=True) as probe_callbacks:
                with transaction.atomic():
                    healthy = _post(client, "approve", rows[:1])
                    assert healthy.status_code == 200
                    assert healthy.json() == {"decided": 1, "ids": [rows[0].pk]}
                    assert EventRegistration.objects.get(pk=rows[0].pk).status == "registered"
                    assert list(fence.values_list("state", "operation_id")) == [("closed", None)]
                    transaction.set_rollback(True)
            assert probe_callbacks == []
        assert _persisted(rows[0]) == before
        assert fence.update(state="open") == 1
        restored = _post(client, "approve", rows)
        assert restored.status_code == 200
        assert restored.json() == {"decided": 2, "ids": [row.pk for row in rows]}
        assert list(EventRegistration.objects.order_by("pk").values_list("status", flat=True)) == ["registered"] * 2
        assert list(EventRegistrationCredential.objects.order_by("registration_id").values_list(
            "registration_id", "generation", "revoked_at")) == [(row.pk, 1, None) for row in rows]
        assert list(Payment.objects.values()) == []
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.registration_approved").count() == 2
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.credential_issued").count() == 2


@pytest.mark.parametrize("key_failure", [False, True])
def test_preparation_failure_blames_only_second_events_dependency_and_restores(
        monkeypatch, django_capture_on_commit_callbacks, key_failure):
    from apps.encryption.brokers.local import LocalMasterKeyBroker
    from apps.encryption.cache import dek_cache
    from apps.encryption.crypto import PiiKeyUnavailable
    from apps.encryption.preparation import prepare_tenants
    from apps.encryption.services import get_or_create_active_dek
    from tests.encryption.conftest import enabled_encryption

    with enabled_encryption():
        space, actor, rows, client = _batch()
        collaborator = _space("bulk-second-event-dependency")
        EventCollaborator.objects.create(event=rows[1].event, makerspace=collaborator, status="accepted")
        # Pre-existing keys isolate the failed command's snapshots from provisioning.
        for tenant in (space, collaborator):
            get_or_create_active_dek(tenant.pk)
        before, attempted = _persisted(rows[0]), []
        unwrap = LocalMasterKeyBroker.unwrap_dek

        def unavailable(broker, wrapped_dek, makerspace_id, version, **kwargs):
            attempted.append(makerspace_id)
            if makerspace_id == collaborator.pk:
                if key_failure:
                    raise PiiKeyUnavailable()
                raise RuntimeError("private broker failure; key locator must never escape")
            return unwrap(broker, wrapped_dek, makerspace_id, version, **kwargs)

        with monkeypatch.context() as fault:
            fault.setattr(LocalMasterKeyBroker, "unwrap_dek", unavailable)
            dek_cache.clear()
            with django_capture_on_commit_callbacks(execute=True) as callbacks:
                refused = _post(client, "approve", rows)
            assert collaborator.pk in attempted
            assert refused.status_code == 409
            assert refused.json() == {"code": "bulk_failed",
                "detail": "Nothing was changed: one item could not be decided.", "failed_id": rows[1].pk,
                "cause": "Protected data is unavailable." if key_failure else "Protected data is temporarily unavailable."}
            assert _persisted(rows[0]) == before
            assert callbacks == []

            # Prove this exact first registration succeeds while E2's broker is
            # still broken. Prepare outside a rollback-only probe transaction.
            with prepare_tenants([space.pk]), preparation.prepare_event_credentials([rows[0].event_id]):
                with django_capture_on_commit_callbacks(execute=True) as probe_callbacks:
                    with transaction.atomic():
                        healthy = _post(client, "approve", rows[:1])
                        assert healthy.status_code == 200
                        assert healthy.json() == {"decided": 1, "ids": [rows[0].pk]}
                        assert EventRegistration.objects.get(pk=rows[0].pk).status == "registered"
                        transaction.set_rollback(True)
                assert probe_callbacks == []
            assert _persisted(rows[0]) == before

        restored = _post(client, "approve", rows)
        assert restored.status_code == 200
        assert restored.json() == {"decided": 2, "ids": [row.pk for row in rows]}
        assert list(EventRegistration.objects.order_by("pk").values_list("status", flat=True)) == ["registered"] * 2
        assert list(EventRegistrationCredential.objects.order_by("registration_id").values_list(
            "registration_id", "generation", "revoked_at")) == [(row.pk, 1, None) for row in rows]
        assert list(Payment.objects.values()) == []
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.registration_approved").count() == 2
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.credential_issued").count() == 2


@pytest.mark.parametrize("platform", [False, True])
def test_batch_boundary_preserves_authorized_cross_tenant_decisions(platform):
    space, actor, rows, _ = _batch()
    other = _space("bulk-other-host")
    other_event = open_event(other, registration_requires_approval=True)
    rows[1].event = other_event
    rows[1].save(update_fields=["event"])
    if platform:
        actor = User.objects.create_superuser("bulk-platform", "platform@example.test", None)
    else:
        assign_builtin_roles(actor, other, "space_manager")
    response = _post(authenticated_client(actor), "approve", rows)
    assert response.status_code == 200
    assert response.json() == {"decided": 2, "ids": [row.pk for row in rows]}
    assert list(EventRegistration.objects.order_by("pk").values_list("status", flat=True)) == ["registered"] * 2
    assert list(EventRegistrationCredential.objects.order_by("registration_id").values_list(
        "registration_id", "generation")) == [(row.pk, 1) for row in rows]
    for tenant in (space, other):
        assert AuditLog.objects.filter(makerspace=tenant, actor=actor, action="event.registration_approved").count() == 1
        assert AuditLog.objects.filter(makerspace=tenant, actor=actor, action="event.credential_issued").count() == 1


def test_bulk_approval_also_prepares_enabled_tenant_encryption_before_domain_locks():
    from tests.encryption.conftest import enabled_encryption

    with enabled_encryption():
        space, actor, rows, client = _batch()
        response = _post(client, "approve", rows)
        assert response.status_code == 200
        assert response.json() == {"decided": 2, "ids": [row.pk for row in rows]}
        assert list(EventRegistration.objects.order_by("pk").values_list("status", flat=True)) == ["registered"] * 2
        assert EventRegistrationCredential.objects.count() == 2
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action="event.registration_approved").count() == 2


@pytest.mark.parametrize("decision,final_status,action", DECISIONS)
def test_later_invalid_registration_rolls_back_real_earlier_decision_and_credentials(
        decision, final_status, action, monkeypatch):
    space, actor, rows, client = _batch()
    rows[1].status = "registered"
    rows[1].save(update_fields=["status"])
    before = _persisted(rows[0])
    service_name = "approve_registration" if decision == "approve" else "reject_registration"
    service = getattr(state, service_name)
    completed = []

    def observed(registration, *, actor):
        result = service(registration, actor=actor)
        completed.append(registration.pk)
        assert result.status == final_status
        assert AuditLog.objects.filter(makerspace=space, actor=actor, action=action).count() == 1
        assert EventRegistrationCredential.objects.count() == (1 if decision == "approve" else 0)
        return result

    monkeypatch.setattr(state, service_name, observed)
    response = _post(client, decision, rows)
    assert completed == [rows[0].pk]
    assert response.status_code == 409
    verb = "approved" if decision == "approve" else "rejected"
    assert response.json() == {"code": "bulk_failed",
        "detail": "Nothing was changed: one item could not be decided.",
        "failed_id": rows[1].pk, "cause": f"This registration cannot be {verb}."}
    assert _persisted(rows[0]) == before


@pytest.mark.parametrize("decision,final_status,action", DECISIONS)
def test_disabled_events_refuses_before_preparation_or_dml_and_restores(
        decision, final_status, action, monkeypatch):
    space, actor, rows, client = _batch()
    enabled = list(space.enabled_modules)
    space.enabled_modules = [module for module in enabled if module != "events"]
    space.save(update_fields=["enabled_modules"])
    before = _persisted(rows[0])
    original = preparation.prepare_event_credentials
    prepared = []

    @contextmanager
    def observed(event_ids):
        prepared.append(set(event_ids))
        with original(event_ids):
            yield

    monkeypatch.setattr(preparation, "prepare_event_credentials", observed)
    with CaptureQueriesContext(connection) as queries:
        refused = _post(client, decision, rows)
    assert refused.status_code == 409
    assert refused.json() == {"code": "bulk_failed",
        "detail": "Nothing was changed: one item could not be decided.", "failed_id": rows[0].pk,
        "cause": {"detail": "events is turned off for this makerspace.",
                  "code": "module_disabled", "module": "events"}}
    assert prepared == []
    assert [query["sql"] for query in queries if query["sql"].lstrip().upper().startswith(
        ("INSERT", "UPDATE", "DELETE"))] == []
    assert _persisted(rows[0]) == before
    space.enabled_modules = enabled
    space.save(update_fields=["enabled_modules"])
    restored = _post(client, decision, rows)
    assert restored.status_code == 200
    assert restored.json() == {"decided": 2, "ids": [row.pk for row in rows]}
    assert prepared[0] == {row.event_id for row in rows}
    assert list(EventRegistration.objects.order_by("pk").values_list("status", flat=True)) == [final_status] * 2
    assert AuditLog.objects.filter(makerspace=space, actor=actor, action=action).count() == 2
