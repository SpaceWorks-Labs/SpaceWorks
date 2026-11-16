"""Real PostgreSQL statement cancellation survives message-masking wrappers."""
import psycopg2
import pytest
from django.db import OperationalError, connection

from apps.data_export import runner
from apps.data_export.runner_queries import is_statement_timeout
from tests.data_export.test_runner import job_for, space, user

pytestmark = pytest.mark.django_db(transaction=True)


def test_psycopg2_export_statement_timeout_becomes_deadline_exceeded(monkeypatch):
    job = job_for(space("sqlstate-export"), user("sqlstate-export-requester"))
    observed = []

    def slow_export_query(dataset, *_args, **_kwargs):
        observed.append(dataset.path)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL statement_timeout = '10ms'")
                cursor.execute("SELECT pg_sleep(1)")
        except OperationalError as exc:
            assert isinstance(exc.__cause__, psycopg2.errors.QueryCanceled)
            assert exc.__cause__.pgcode == "57014"
            # The old text fallback must not make a broken SQLSTATE check pass.
            raise OperationalError("Export query cancelled") from exc
        pytest.fail("PostgreSQL did not cancel the slow export query")

    monkeypatch.setattr(runner, "_read_dataset", slow_export_query)
    with pytest.raises(runner.ExportDeadlineExceeded) as caught:
        runner.build_archive(job)
    assert caught.value.dataset == observed[0]
    assert caught.value.rows_completed == 0
    masked = caught.value.__cause__
    assert str(masked) == "Export query cancelled"
    assert is_statement_timeout(masked) is True
    assert is_statement_timeout(masked.__cause__) is True
    assert is_statement_timeout(masked.__cause__.__cause__) is True
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone() == (1,)
