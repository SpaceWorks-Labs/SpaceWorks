from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from django.db import close_old_connections, connection
import pytest
from apps.events.contributions import shift_workflow
from apps.events.contributions.errors import ProgrammeError
from apps.events.contributions.models import EventShiftSignup
from tests.events.programme.contributions.helpers import setup_shift


@pytest.mark.django_db(transaction=True)
def test_last_shift_place_is_serialized_and_fifo_waitlisted(settings):
    _, event, _, shift, users, roles, _ = setup_shift(settings)

    def apply(index):
        close_old_connections()
        try:
            return shift_workflow.apply(actor=users[index], event_id=event.pk, shift_id=shift.pk,
                payload={"operation_id": uuid4(), "expected_version": shift.version,
                         "role_assignment_id": roles[index].pk}).row.state
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        states = list(pool.map(apply, [0, 1]))
    assert sorted(states) == ["approved", "waitlisted"]
    assert EventShiftSignup.objects.filter(shift=shift, state="approved").count() == 1


@pytest.mark.django_db
def test_identical_retry_creates_one_signup_changed_digest_conflicts(settings):
    _, event, _, shift, users, roles, _ = setup_shift(settings)
    payload = {"operation_id": uuid4(), "expected_version": shift.version, "role_assignment_id": roles[0].pk}
    first = shift_workflow.apply(actor=users[0], event_id=event.pk, shift_id=shift.pk, payload=payload)
    again = shift_workflow.apply(actor=users[0], event_id=event.pk, shift_id=shift.pk, payload=payload)
    assert first.row.pk == again.row.pk and again.replayed
    with pytest.raises(ProgrammeError) as error:
        shift_workflow.apply(actor=users[0], event_id=event.pk, shift_id=shift.pk,
                             payload={**payload, "expected_version": 999})
    assert error.value.detail["code"] == "idempotency_conflict"
    assert EventShiftSignup.objects.filter(shift=shift).count() == 1


@pytest.mark.django_db
def test_mapped_write_fence_precedes_event_for_update(settings):
    _, event, _, shift, users, roles, _ = setup_shift(settings)
    queries = []
    def capture(execute, sql, params, many, context):
        queries.append(sql)
        return execute(sql, params, many, context)
    with connection.execute_wrapper(capture):
        shift_workflow.apply(actor=users[0], event_id=event.pk, shift_id=shift.pk,
            payload={"operation_id": uuid4(), "expected_version": shift.version, "role_assignment_id": roles[0].pk})
    # The shared write boundary checks the tenant fence row under its advisory lock.
    fence = next(i for i, sql in enumerate(queries) if "pii_assert_mapped_write_allowed" in sql
                 or '"encryption_piimakerspacewritefence"' in sql)
    event_lock = next(i for i, sql in enumerate(queries) if '"events_event"' in sql and "FOR UPDATE" in sql)
    assert fence < event_lock
