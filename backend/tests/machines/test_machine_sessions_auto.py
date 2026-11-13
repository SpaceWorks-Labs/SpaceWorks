"""L23 (#158.2c/.5/.6): device sessions, the forgot-to-stop sweep, reports and notices."""

from datetime import datetime, timedelta, timezone as dt_timezone
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.machines import sessions_device
from apps.machines.models import MachineSession, MakerspaceMachineTypePolicy
from apps.machines.sessions_sweep import due_stop, run_session_sweep
from apps.payments.models import Payment
from tests.machines.eta_helpers import running
from tests.machines.session_helpers import check_in, features, open_session, session_world
from tests.rbac_f6_helpers import community_member

pytestmark = pytest.mark.django_db


def device_job(w, job, *, minutes=None):
    return SimpleNamespace(pk="00000000-0000-0000-0000-00000000abcd", makerspace=w.space, machine=job.assigned_machine,
                           service_request=job, service_request_id=job.pk, actual_minutes=minutes)


def test_device_reports_open_and_close_an_attributed_job_session_billed_through_the_job():
    w = session_world("dev-attr", billing=False)
    job = running(w, w.machines[0], 30, started_ago=5, member=w.member)
    opened = sessions_device.on_agent_report(device_job(w, job), "started")
    assert opened.source == "device" and opened.member_id == w.member.pk and not opened.billable
    assert sessions_device.on_agent_report(device_job(w, job), "started") is None  # repeat is a no-op
    closed = sessions_device.on_agent_report(device_job(w, job, minutes=42), "completed")
    assert (closed.stop_reason, closed.duration_minutes, closed.flagged) == ("device", 42, False)
    assert not Payment.objects.filter(subject_type="machine_session", subject_id=closed.pk).exists()


def test_device_session_with_no_member_of_the_space_is_held_unattributed():
    w = session_world("dev-unattr", billing=False)
    from tests.machines.eta_helpers import owner
    job = running(w, w.machines[0], 30, started_ago=5, member=owner("dev-unattr-outsider"))
    opened = sessions_device.on_agent_report(device_job(w, job), "started")
    assert opened.member_id is None
    closed = sessions_device.on_agent_report(device_job(w, job, minutes=10), "failed")
    from apps.machines.sessions_state import needs_review
    assert needs_review(closed)


def test_device_hook_is_inert_while_sessions_are_off():
    w = session_world("dev-off", billing=False)
    features(w.space, remove={"machines.sessions"})
    job = running(w, w.machines[0], 30, started_ago=5, member=w.member)
    assert sessions_device.on_agent_report(device_job(w, job), "started") is None
    assert not MachineSession.objects.exists()


def test_sweep_stops_at_max_length_and_flags():
    w = session_world("sweep-max")
    MakerspaceMachineTypePolicy.objects.create(makerspace=w.space, machine_type=w.kind, session_max_minutes=60)
    row = open_session(w, minutes_ago=150)
    counts = run_session_sweep()
    row.refresh_from_db()
    assert counts["auto_stopped"] == 1
    assert (row.stop_reason, row.flagged, row.duration_minutes) == ("max_length", True, 60)


def test_sweep_stops_at_check_out():
    w = session_world("sweep-out", checked_in=False)
    check_in(w.space, w.membership, minutes_ago=60, ended_minutes_ago=20)
    row = open_session(w, minutes_ago=50)
    run_session_sweep()
    row.refresh_from_db()
    assert row.stop_reason == "check_out" and row.flagged and row.duration_minutes == 30


def test_sweep_leaves_a_checked_in_session_running():
    w = session_world("sweep-in")
    row = open_session(w, minutes_ago=20)
    run_session_sweep()
    row.refresh_from_db()
    assert row.ended_at is None


def test_due_stop_takes_closing_time_from_opening_hours():
    w = session_world("sweep-close")
    w.space.timezone = "UTC"
    w.space.opening_hours = {"weekly": {}, "exceptions": {"2026-10-20": [{"start": "08:00", "end": "12:00"}]}}
    w.space.save(update_fields=["timezone", "opening_hours"])
    started = datetime(2026, 10, 20, 10, 0, tzinfo=dt_timezone.utc)
    row = SimpleNamespace(makerspace=w.space, machine_type=w.kind, member_id=None, makerspace_id=w.space.pk,
                          started_at=started)
    assert due_stop(row, now=started + timedelta(hours=1)) is None
    reason, at = due_stop(row, now=started + timedelta(hours=3))
    assert reason == "closing" and at == datetime(2026, 10, 20, 12, 0, tzinfo=dt_timezone.utc)


def test_auto_stop_notifies_the_member_and_staff():
    from apps.integrations.models import NotificationEnvelope
    w = session_world("sweep-notice")
    row = open_session(w, minutes_ago=300)
    run_session_sweep()
    envelopes = NotificationEnvelope.objects.filter(source_kind="machines.session", source_id=row.pk)
    assert envelopes.filter(audience="requester", recipient=w.member).exists()


def test_reports_cover_sessions_utilisation_busiest_idle_and_flagged():
    from apps.operations.reports import report_rows
    w = session_world("rep-sessions")
    other = community_member(w.space, "rep-other")
    from apps.machines.sessions_service import stop
    first = open_session(w, minutes_ago=120)
    stop(first, actor=w.member, reason="member", at=first.started_at + timedelta(minutes=60))
    flagged = open_session(w, member=other.user, minutes_ago=50)
    stop(flagged, actor=None, reason="max_length", at=flagged.started_at + timedelta(minutes=40))
    window = (timezone.now() - timedelta(days=1), timezone.now())
    for key in ("machine-sessions", "machine-session-utilisation", "machine-session-busiest", "machine-session-idle",
                "machine-session-flagged"):
        rows = report_rows(key, w.space.pk, date_range=window, actor=w.staff)
        assert rows, key
    sessions = report_rows("machine-sessions", w.space.pk, date_range=window, actor=w.staff)
    assert len(sessions) == 3  # header + two sessions
    idle = report_rows("machine-session-idle", w.space.pk, date_range=window, actor=w.staff)
    assert any(w.machines[1].name in [str(cell) for cell in row] for row in idle[1:])
    flagged_rows = report_rows("machine-session-flagged", w.space.pk, date_range=window, actor=w.staff)
    assert len(flagged_rows) == 2


def test_reports_refuse_while_sessions_are_off():
    from apps.operations.reports import report_rows
    w = session_world("rep-off")
    features(w.space, remove={"machines.sessions"})
    with pytest.raises(Exception):
        report_rows("machine-session-idle", w.space.pk, actor=w.staff)
