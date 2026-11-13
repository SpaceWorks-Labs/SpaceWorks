"""Review fix: a malformed control record fails clearly before any restore write."""
import json
import uuid
from datetime import datetime, timezone as dt_timezone

import pytest
from django.core.management.base import CommandError

from apps.backup.models import RestoreOperation
from apps.backup.restore_control_records import _control_fields, rehydrate_control_record


def test_missing_or_unknown_decision_is_a_command_error():
    for control in ({}, {"decision": "maybe"}, []):
        with pytest.raises(CommandError, match="restore decision"):
            _control_fields(control)


def test_deadline_is_parsed_to_an_aware_datetime():
    decision, deadline = _control_fields({"decision": "proceed", "decision_deadline_at": "2026-11-09T10:00:00+00:00"})
    assert decision == "proceed"
    assert deadline == datetime(2026, 11, 9, 10, tzinfo=dt_timezone.utc)
    assert _control_fields({"decision": "abort", "decision_deadline_at": None}) == ("abort", None)


@pytest.mark.parametrize("raw", ["not-a-date", "2026-11-09T10:00:00", 12])
def test_bad_or_naive_deadline_is_a_command_error(raw):
    with pytest.raises(CommandError, match="decision_deadline_at"):
        _control_fields({"decision": "proceed", "decision_deadline_at": raw})


@pytest.mark.django_db
def test_rehydrate_refuses_before_writing(tmp_path):
    control = tmp_path / "control.json"
    manifest = tmp_path / "manifest.json"
    control.write_text(json.dumps({"restore_diff": {}}), encoding="utf-8")
    manifest.write_text("{}", encoding="utf-8")
    restore_id = uuid.uuid4()
    with pytest.raises(CommandError):
        rehydrate_control_record(restore_id, {"archive_id": str(uuid.uuid4()), "kind": "classic",
                                              "control_record": str(control), "manifest": str(manifest)})
    assert not RestoreOperation.objects.filter(pk=restore_id).exists()
