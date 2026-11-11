from datetime import datetime, timedelta, UTC
from types import SimpleNamespace

import pytest

from apps.events.submissions.errors import SubmissionError
from apps.events.submissions.project_validation import validate_project_patch
from apps.events.submissions.retention import capture_disposition
from apps.events.submissions.workflow import canonical_digest


@pytest.mark.parametrize("patch", [{"state": "judged"}, {"title": "x" * 201}, {"public_requested": "true"},
    {"asset_ids": [True]}, {"asset_ids": [1, 1]}, {"track_ids": [-1]}, {"tech_tags": [" "]},
    {"ai_declaration": {"used": True, "details": ""}}, {"reuse_declaration": {"used": False}}])
def test_project_boundary_refuses_unknown_status_writes_and_bad_inputs(patch):
    with pytest.raises(SubmissionError):
        validate_project_patch(patch)


def test_canonical_operation_digest_is_order_stable_and_rejects_nan_and_unbounded_content():
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})
    assert canonical_digest({"version": 1}) != canonical_digest({"version": 2})
    for value in ({"float": float("nan")}, {"oversize": "x" * (256 * 1024)}):
        with pytest.raises(SubmissionError):
            canonical_digest(value)


def test_capture_distinguishes_expected_expired_absence_from_missing_ready_corruption():
    now = datetime.now(UTC)
    assert capture_disposition(SimpleNamespace(expired_at=None, expires_at=now-timedelta(seconds=1), state="ready"), now=now) == "retention_finalization_required"
    assert capture_disposition(SimpleNamespace(expired_at=now, expires_at=None, state="expired"), now=now) == "expected_expired"
    assert capture_disposition(SimpleNamespace(expired_at=None, expires_at=now+timedelta(days=1), state="ready"), now=now) == "required"
