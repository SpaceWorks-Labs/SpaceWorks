import uuid

import psycopg2
import pytest
from psycopg2.extensions import make_dsn

from apps.backup.managed.operation_lock import managed_operation_lock
from apps.backup.operation_lock import OperationLockUnavailable
from config.cloud_database import django_database_spec


pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def environment(monkeypatch):
    # These tests isolate live exclusion/loss from the separately tested binding
    # checks. The isolated harness connects as its DB owner for termination tests.
    monkeypatch.setattr("apps.backup.managed.admission.assert_binding", lambda *args: {})
    return {
        "DATABASE_URL": make_dsn(**django_database_spec().kwargs()),
        "DATABASE_CONNECTION_MODE": "direct", "SPACEWORKS_DEPLOYMENT_ID": str(uuid.uuid4()),
    }


def test_all_managed_operation_contenders_share_one_nonblocking_lock(environment):
    # get_connection_params may include options; database_spec deliberately owns
    # options, so use the minimal explicit DSN from the connection facts.
    from psycopg2.extensions import parse_dsn
    params = parse_dsn(environment["DATABASE_URL"])
    params.pop("options", None)
    environment["DATABASE_URL"] = make_dsn(**params)
    with managed_operation_lock(environ=environment) as first:
        first.assert_valid()
        with pytest.raises(OperationLockUnavailable):
            with managed_operation_lock(environ=environment):
                pytest.fail("second operation admitted")
    with managed_operation_lock(environ=environment) as after:
        after.assert_valid()


def test_operation_guard_loss_aborts_before_further_effects(environment):
    from psycopg2.extensions import parse_dsn
    params = parse_dsn(environment["DATABASE_URL"])
    params.pop("options", None)
    environment["DATABASE_URL"] = make_dsn(**params)
    other = psycopg2.connect(**params)
    other.autocommit = True
    effects = []
    try:
        with pytest.raises(OperationLockUnavailable):
            with managed_operation_lock(environ=environment) as guard:
                with other.cursor() as cursor:
                    cursor.execute("SELECT pg_terminate_backend(%s)", [guard.pid])
                guard.assert_valid()
                effects.append("should-not-run")
    finally:
        other.close()
    assert effects == []
