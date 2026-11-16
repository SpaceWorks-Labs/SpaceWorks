"""SECURITY-REVIEW M4 / decision 336(h): adapter-reported session minutes are bounded by the wall clock and the cap.

An honest report is billed as reported. Over-reporting (overcharging the member), under-reporting (free use) and a
report beyond the session cap bill the bounded wall-clock time and hold the session for staff review, so no charge is
final until staff confirm or amend it.
"""
import uuid
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.machines import sessions_state as state
from apps.machines.models import MachineSession
from tests.parity_0120.adapter_api.adapter_case import adapter_case, plain_member

pytestmark = pytest.mark.django_db(transaction=True)


def _session(case, minutes_ago):
    member = plain_member(f"f3-min-{uuid.uuid4().hex[:6]}", case["space"])
    return MachineSession.objects.create(
        makerspace=case["space"], machine=case["machine"], machine_type=case["machine"].machine_type, member=member,
        source="device", started_at=timezone.now() - timedelta(minutes=minutes_ago),
        device_job_ref=f"adapter:{case['device'].pk}")


def _stop(case, session, **body):
    return case["sim"].post(f"sessions/{session.pk}/stop", {"reason": "member", **body})


def _flag_audit(session):
    return AuditLog.objects.filter(action="devices.adapter_session_stopped", meta__session_id=session.pk,
                                   meta__minutes_flagged=True).first()


def test_an_honest_report_is_billed_as_reported_and_not_held():
    case = adapter_case("f3-min-honest")
    session = _session(case, 30)
    response = _stop(case, session, active_minutes=27, idle_minutes=2)
    assert response.status_code == 200, response.data
    session.refresh_from_db()
    assert response.data["minutes"] == session.duration_minutes == 29
    assert session.flagged is False and not state.needs_review(session)
    assert _flag_audit(session) is None


def test_over_reporting_bills_the_wall_clock_and_holds_for_review():
    case = adapter_case("f3-min-over")
    session = _session(case, 30)
    response = _stop(case, session, active_minutes=100000, idle_minutes=100000)
    assert response.status_code == 200, response.data
    session.refresh_from_db()
    assert session.duration_minutes == 30
    assert session.flagged is True and state.needs_review(session)
    row = _flag_audit(session)
    assert row is not None and row.meta["reported_minutes"] == 200000 and row.meta["billed_minutes"] == 30


def test_under_reporting_cannot_give_use_away():
    case = adapter_case("f3-min-under")
    session = _session(case, 60)
    assert _stop(case, session, active_minutes=0, idle_minutes=0).status_code == 200
    session.refresh_from_db()
    assert session.duration_minutes == 60 and session.flagged is True
    assert _flag_audit(session).meta["reported_minutes"] == 0


def test_a_report_beyond_the_session_cap_is_bounded_by_the_cap():
    case = adapter_case("f3-min-cap")
    configured = case["client"].put(reverse("devices:admin-adapter-binding-config", args=[case["binding_id"]]),
                                    {"max_session_minutes": 10}, format="json")
    assert configured.status_code == 200, configured.data
    session = _session(case, 30)
    assert _stop(case, session, active_minutes=30, idle_minutes=0).status_code == 200
    session.refresh_from_db()
    assert session.duration_minutes == 10 and session.flagged is True


def test_no_reported_minutes_keeps_the_wall_clock_unflagged():
    case = adapter_case("f3-min-none")
    session = _session(case, 15)
    assert _stop(case, session).status_code == 200
    session.refresh_from_db()
    assert session.duration_minutes == 15 and session.flagged is False


def test_small_rounding_differences_are_within_tolerance():
    from apps.devices.services_adapter_sessions import checked_minutes
    case = adapter_case("f3-min-unit")
    session = _session(case, 20)
    now = timezone.now()
    assert checked_minutes(case["device"], session, 21, now) == (21, False)  # +1 minute of skew
    assert checked_minutes(case["device"], session, 18, now) == (18, False)  # within 10% / 2 minutes under
    assert checked_minutes(case["device"], session, 22, now) == (20, True)
    assert checked_minutes(case["device"], session, None, now) == (None, False)
