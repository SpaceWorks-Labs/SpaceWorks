"""COVERAGE-BE: refusal branches of the export runner and its query helpers, with exact messages."""
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.db import OperationalError
from django.db.models import Q
from django.utils import timezone

from apps.data_export import runner
from apps.data_export.errors import ExportIntegrityError
from apps.data_export.runner import ExportDeadlineExceeded
from apps.data_export.runner_queries import after_keyset, is_statement_timeout, key_value
from apps.data_export.types import Fidelity
from apps.makerspaces.models import Makerspace

pytestmark = pytest.mark.django_db(transaction=True)


def test_existing_snapshot_requires_an_active_transaction():
    space = Makerspace.objects.create(name="runner-cov", slug="runner-cov")
    job = SimpleNamespace(
        fidelity="REDACTED", deadline_at=timezone.now() + timedelta(minutes=5),
        makerspace_id=space.pk, makerspace=space)
    with pytest.raises(ExportIntegrityError, match="existing export snapshot requires an active transaction"):
        runner.build_archive(job, existing_snapshot=True)


def test_check_deadline_raises_only_at_or_after_the_deadline():
    runner._check_deadline("inventory/x.csv", 3, 100.0, lambda: 99.9)
    for now in (100.0, 100.1):
        with pytest.raises(ExportDeadlineExceeded) as caught:
            runner._check_deadline("inventory/x.csv", 3, 100.0, lambda: now)
        assert (caught.value.dataset, caught.value.rows_completed) == ("inventory/x.csv", 3)
        assert "after 3 rows; last dataset: inventory/x.csv" in str(caught.value)


def _transfer(pk, owner, source):
    return SimpleNamespace(pk=pk, makerspace_id=owner, source_makerspace_id=source)


def test_stock_transfer_owner_must_match_source_participant():
    dataset = SimpleNamespace(model="operations.StockTransfer")
    runner._validate_dataset_integrity(dataset, [_transfer(1, 5, 5), _transfer(2, 5, None)], 5)
    with pytest.raises(ExportIntegrityError, match=r"StockTransfer row 3 owner 5 disagrees with source participant 6"):
        runner._validate_dataset_integrity(dataset, [_transfer(3, 5, 6)], 5)
    # other models are never inspected
    runner._validate_dataset_integrity(SimpleNamespace(model="inventory.Category"), [object()], 5)


def _snapshot_row(ids):
    return SimpleNamespace(pk=1, sealed_member_ids=ids)


def test_sealed_member_ids_must_be_positive_ints_for_portable_only():
    dataset = SimpleNamespace(fidelity=Fidelity.PORTABLE, model="events.SubmissionSnapshot")
    for bad in ([0], [-3], ["7"], [True]):
        with pytest.raises(ExportIntegrityError, match="Invalid sealed programme member reference"):
            runner._collect_semantic_user(dataset, _snapshot_row(bad), set(), [])
    candidates, values = set(), []
    runner._collect_semantic_user(dataset, _snapshot_row([4, 9]), candidates, values)
    assert candidates == {4, 9} and [(f, v) for _r, f, _e, v in values] == [("sealed_member_ids", 4), ("sealed_member_ids", 9)]
    assert all(edge.raw for _r, _f, edge, _v in values)
    readable = SimpleNamespace(fidelity=Fidelity.REDACTED, model="events.SubmissionSnapshot")
    candidates, values = set(), []
    runner._collect_semantic_user(readable, _snapshot_row([0]), candidates, values)
    assert candidates == set() and values == []


def _audit_row(target_type, target_id):
    return SimpleNamespace(pk=8, target_type=target_type, target_id=target_id)


def test_audit_user_targets_join_the_readable_closure_and_bad_ids_are_ignored():
    dataset = SimpleNamespace(fidelity=Fidelity.REDACTED, model="audit.AuditLog")
    candidates, values = set(), []
    runner._collect_semantic_user(dataset, _audit_row("accounts.User", "7"), candidates, values)
    assert candidates == {7} and [(f, v) for _r, f, _e, v in values] == [("target_id", 7)]
    for ignored in (_audit_row("accounts.User", "not-a-number"), _audit_row("inventory.Product", "7"),
                    _audit_row("accounts.User", None)):
        candidates, values = set(), []
        runner._collect_semantic_user(dataset, ignored, candidates, values)
        assert candidates == set() and values == []


def test_portable_run_refuses_a_user_target_with_a_non_numeric_id(monkeypatch):
    # PORTABLE audit decisions carry no SemanticUserRef today, so this guard is defensive; prove it by
    # declaring the user ref for the portable fidelity.
    from apps.data_export.types import SemanticUserRef
    key = (Fidelity.PORTABLE, "audit.AuditLog", "target_type+target_id")
    monkeypatch.setitem(runner.SEMANTIC_REFERENCES, key, (SemanticUserRef("audit.AuditLog", "x", "y"),))
    dataset = SimpleNamespace(fidelity=Fidelity.PORTABLE, model="audit.AuditLog")
    with pytest.raises(ExportIntegrityError, match=r"audit.AuditLog row 8 has invalid target_id='abc'"):
        runner._collect_semantic_user(dataset, _audit_row("accounts.User", "abc"), set(), [])


# ------------------------------------------------------------- runner_queries
def test_after_keyset_builds_a_strict_lexicographic_condition():
    assert after_keyset(("a", "b"), (1, 2)) == Q(a__gt=1) | Q(a=1, b__gt=2)
    assert after_keyset(("pk",), (5,)) == Q(pk__gt=5)


def test_key_value_resolves_by_field_name_or_attname():
    from apps.data_export.models import DataExportJob
    row = DataExportJob(requested_by_id=12, fidelity="REDACTED")
    assert key_value(row, "requested_by") == 12
    assert key_value(row, "requested_by_id") == 12
    assert key_value(row, "fidelity") == "REDACTED"
    with pytest.raises(StopIteration):
        key_value(row, "no_such_column")


def test_statement_timeout_detected_by_sqlstate_or_message():
    class Cause(Exception):
        sqlstate = "57014"
    by_state = OperationalError("boom")
    by_state.__cause__ = Cause()
    assert is_statement_timeout(by_state) is True
    assert is_statement_timeout(OperationalError("canceling statement due to Statement Timeout")) is True
    assert is_statement_timeout(OperationalError("connection refused")) is False
