"""GAP2 M3 (#142 OQ-6): the at-risk flag on machine jobs. A flag only; needed-by never reorders. Local only."""

from datetime import date, datetime, timedelta, timezone as utc
from types import SimpleNamespace

import pytest

from apps.machines import job_risk
from apps.machines.models import MachineServiceRequest
from apps.makerspaces.local_time import local_now
from tests.machines.eta_helpers import approved, job, world
from tests.return_helpers import authenticated_client

TODAY = date(2026, 11, 10)
SPACE = SimpleNamespace(timezone="Asia/Kolkata")


def row(status="accepted", needed_by=TODAY + timedelta(days=3)):
    return SimpleNamespace(status=status, needed_by=needed_by)


def eta(finish):
    return {"estimated_finish_at": finish}


def test_no_needed_by_or_a_closed_job_is_never_at_risk():
    assert job_risk.reasons(row(needed_by=None), None, TODAY, SPACE) == []
    for status in ("completed", "collected", "uncollected", "rejected", "failed", "cancelled"):
        assert job_risk.reasons(row(status, TODAY - timedelta(days=5)), None, TODAY, SPACE) == []


def test_a_passed_date_is_flagged_for_every_open_state():
    for status in job_risk.OPEN:
        assert job_risk.reasons(row(status, TODAY - timedelta(days=1)), None, TODAY, SPACE) == [job_risk.PASSED]


def test_the_forecast_is_compared_with_the_end_of_the_needed_by_day_in_local_time():
    needed = TODAY + timedelta(days=1)
    # 23:00 local on the needed-by day is still in time; 00:30 local the day after is late.
    on_time = datetime(2026, 11, 11, 17, 30, tzinfo=utc.utc)
    late = datetime(2026, 11, 11, 19, 0, tzinfo=utc.utc)
    assert job_risk.reasons(row(needed_by=needed), eta(on_time), TODAY, SPACE) == []
    assert job_risk.reasons(row(needed_by=needed), eta(late), TODAY, SPACE) == [job_risk.LATE]
    assert job_risk.reasons(row(needed_by=needed), eta(late.isoformat()), TODAY, SPACE) == [job_risk.LATE]


def test_without_a_forecast_only_a_date_today_or_tomorrow_is_flagged_and_never_once_running():
    assert job_risk.reasons(row(needed_by=TODAY + timedelta(days=1)), eta(None), TODAY, SPACE) == [job_risk.SOON]
    assert job_risk.reasons(row(needed_by=TODAY), None, TODAY, SPACE) == [job_risk.SOON]
    assert job_risk.reasons(row(needed_by=TODAY + timedelta(days=2)), None, TODAY, SPACE) == []
    assert job_risk.reasons(row("in_progress", TODAY), None, TODAY, SPACE) == []


@pytest.mark.django_db
def test_the_staff_board_carries_the_reasons_and_needed_by_does_not_reorder():
    w = world("gap-m3-board")
    first = approved(w, 30, created=-60, title="First")
    second = approved(w, 30, created=-30, title="Second")
    today = local_now(w.space).date()
    MachineServiceRequest.objects.filter(pk=second.pk).update(needed_by=today - timedelta(days=1))
    MachineServiceRequest.objects.filter(pk=first.pk).update(needed_by=today + timedelta(days=30))
    pending = job(w, "Pending soon")
    MachineServiceRequest.objects.filter(pk=pending.pk).update(needed_by=today)
    response = authenticated_client(w.staff).get(
        f"/api/v1/admin/makerspaces/{w.space.pk}/machine-service/board?machine_type_id={w.kind.pk}")
    assert response.status_code == 200, response.content
    body = response.json()
    rows = {item["id"]: item for column in ("queue", "review") for item in body[column]}
    rows.update({item["id"]: item for lane in body["lanes"] for item in lane["assigned"]})
    assert rows[second.pk]["at_risk_reasons"] == ["needed_by_passed"]
    assert rows[first.pk]["at_risk_reasons"] == []
    assert rows[pending.pk]["at_risk_reasons"] in (["needed_by_soon"], ["eta_after_needed_by"], [])
    queue_ids = [item["id"] for item in body["queue"]]
    assert queue_ids.index(first.pk) < queue_ids.index(second.pk)
    assert MachineServiceRequest.objects.get(pk=second.pk).queued_at == second.queued_at  # never reordered
