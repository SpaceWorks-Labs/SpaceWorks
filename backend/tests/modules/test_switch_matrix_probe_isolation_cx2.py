"""Probe rollback must preserve preparation, callbacks and the SQL write fence."""
import pytest
from django.db import DataError, connection, transaction

from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.events.credentials.preparation import prepare_event_credentials
from apps.events.website_preparation import prepared_page_write
from apps.transaction_guards import in_domain_transaction
from tests.modules.switch_matrix_object_contracts import OPERATIONS
from tests.modules import switch_matrix_object_helpers as helpers

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("native", [False, True], ids=["browser", "native"])
@pytest.mark.parametrize("key", ["events", "events.website"])
def test_website_probe_has_no_added_atomic_block_and_restores_rows_and_audits(native, key, monkeypatch):
    blocks = tuple(connection.atomic_blocks)
    send, seen = helpers.request, []

    def observe(*args):
        assert tuple(connection.atomic_blocks) == blocks
        assert in_domain_transaction() is False
        response = send(*args)
        seen.append(helpers.response_pair(response))
        return response

    monkeypatch.setattr(helpers, "request", observe)
    index = next(i for i, op in enumerate(OPERATIONS)
                 if op.name == "admin-event-website-content" and op.method == "PUT")
    helpers.run_object_case((index, key, native))
    assert seen == [(200, None), (404, "feature_disabled" if "." in key else "module_disabled"), (200, None)]
    assert tuple(connection.atomic_blocks) == blocks


@pytest.mark.parametrize("failure", [None, ValueError, DataError])
def test_probe_rollback_discards_writes_and_own_callbacks_but_preserves_outer_callbacks(failure):
    space, _client, objects = helpers.object_world(False)
    actor = objects["stocktake"].started_by
    before, audits = helpers.retained(objects), AuditLog.objects.count()
    callbacks = []
    transaction.on_commit(lambda: callbacks.append("outer"))
    outer = list(connection.run_on_commit)
    blocks, savepoints = list(connection.atomic_blocks), list(connection.savepoint_ids)

    def probe():
        with helpers.rolled_back():
            assert connection.atomic_blocks == blocks
            assert in_domain_transaction() is False
            type(objects["box"]).objects.filter(pk=objects["box"].pk).update(label="Changed")
            record(actor, "test.probe_changed", makerspace=space, target=objects["box"])
            with transaction.atomic():
                transaction.on_commit(lambda: callbacks.append("probe"))
            assert AuditLog.objects.count() == audits + 1
            if failure is DataError:
                # A caught SQL error must not poison the enclosing test transaction.
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1 / 0")
                except DataError:
                    transaction.set_rollback(True)
                    raise
            if failure:
                raise failure("probe failure")

    if failure:
        with pytest.raises(failure) as caught:
            probe()
        assert type(caught.value) is failure
        assert str(caught.value).strip() == ("division by zero" if failure is DataError else "probe failure")
    else:
        probe()
    assert helpers.retained(objects) == before
    assert AuditLog.objects.count() == audits
    assert connection.run_on_commit == outer
    assert callbacks == []
    assert connection.atomic_blocks == blocks
    assert connection.savepoint_ids == savepoints
    assert connection.needs_rollback is False


@pytest.mark.parametrize("kind,message", [
    ("credentials", "Prepare credential material before domain locks."),
    ("website", "Prepare website assets before domain transactions."),
])
def test_real_caller_atomic_still_trips_the_unmodified_preparation_guard(kind, message):
    with transaction.atomic():
        assert in_domain_transaction() is True
        with pytest.raises(RuntimeError) as caught:
            if kind == "credentials":
                with prepare_event_credentials(()):
                    pytest.fail("Credential preparation accepted a domain transaction")
            else:
                prepared_page_write(lambda target, **kwargs: None)(None, actor=None)
        assert type(caught.value) is RuntimeError
        assert str(caught.value) == message


def test_probe_rejects_a_caller_held_domain_transaction_instead_of_hiding_it():
    with transaction.atomic():
        with pytest.raises(AssertionError) as caught:
            with helpers.rolled_back():
                pytest.fail("Probe accepted a domain transaction")
        assert str(caught.value).split("\n", 1)[0] == (
            "Object probes require Django TestCase isolation without a caller-held domain transaction"
        )


def test_sql_write_fence_still_rejects_even_a_transactional_write():
    space, _client, objects = helpers.object_world(False)
    before, audits = helpers.retained(objects), AuditLog.objects.count()
    with connection.execute_wrapper(helpers._no_write):
        with pytest.raises(AssertionError) as caught:
            # Roll back Django's ORM error state before checking retained rows.
            with transaction.atomic():
                type(objects["box"]).objects.filter(pk=objects["box"].pk).update(label="Forbidden")
        assert type(caught.value) is AssertionError
        assert str(caught.value).split("\n", 1)[0] == "UPDATE"
    assert helpers.retained(objects) == before
    assert AuditLog.objects.count() == audits


@pytest.mark.django_db(transaction=True)
def test_other_lanes_autocommit_callers_keep_their_existing_rollback_contract():
    space, _client, objects = helpers.object_world(False)
    before, audits = helpers.retained(objects), AuditLog.objects.count()
    callbacks = []
    assert connection.get_autocommit() is True
    with helpers.rolled_back():
        type(objects["box"]).objects.filter(pk=objects["box"].pk).update(label="Temporary")
        record(objects["stocktake"].started_by, "test.probe_changed", makerspace=space, target=objects["box"])
        transaction.on_commit(lambda: callbacks.append("probe"))
        assert AuditLog.objects.count() == audits + 1
        assert in_domain_transaction() is True
    assert connection.get_autocommit() is True
    assert helpers.retained(objects) == before
    assert AuditLog.objects.count() == audits
    assert callbacks == []
