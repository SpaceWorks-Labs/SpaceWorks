"""Research P1-4: loan due instants against the space's opening hours (`due_policy`)."""

from datetime import datetime, timezone as dt_timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from apps.hardware_requests import workflow
from apps.hardware_requests.due_policy import closed_notice, effective_due
from apps.hardware_requests.models import PublicToolLoan
from apps.hardware_requests.models_loans import LoanReservationPolicy
from apps.hardware_requests.pickup_windows import deadline_at_accept
from tests.hardware_requests.loan_policy_helpers import setup_loan
from tests.return_helpers import make_member

IST = ZoneInfo("Asia/Kolkata")
WORKDAYS = {day: [{"start": "09:00", "end": "17:00"}] for day in ("mon", "tue", "wed", "thu", "fri")}
HOURS = {"weekly": WORKDAYS}


def ist(*args):
    return datetime(*args, tzinfo=IST)


def space(hours=HOURS, tz="Asia/Kolkata"):
    return SimpleNamespace(timezone=tz, opening_hours=hours)


def test_closed_weekend_rolls_forward_to_monday_opening_plus_grace_in_space_local_time():
    # 2026-11-14 is a Saturday; the space reopens Monday 09:00 IST (03:30 UTC) and the
    # one-hour return grace (decision 219b) makes the due 10:00 IST (04:30 UTC).
    rolled = effective_due(space(), ist(2026, 11, 14, 12, 0))
    assert rolled == datetime(2026, 11, 16, 4, 30, tzinfo=dt_timezone.utc)


def test_open_instant_and_the_closing_instant_are_kept():
    assert effective_due(space(), ist(2026, 11, 16, 10, 0)) == ist(2026, 11, 16, 10, 0)
    assert effective_due(space(), ist(2026, 11, 13, 17, 0)) == ist(2026, 11, 13, 17, 0)
    assert effective_due(space(), ist(2026, 11, 13, 17, 1)) == ist(2026, 11, 16, 10, 0)


def test_open_and_closed_are_judged_in_the_space_zone_not_utc():
    # 05:00 UTC Monday is 10:30 IST: open, although 05:00 would be closed in UTC.
    morning = datetime(2026, 11, 16, 5, 0, tzinfo=dt_timezone.utc)
    assert effective_due(space(), morning) == morning
    # 02:00 UTC Monday is 07:30 IST: before opening, so it moves to 09:00 IST + grace.
    early = datetime(2026, 11, 16, 2, 0, tzinfo=dt_timezone.utc)
    assert effective_due(space(), early) == ist(2026, 11, 16, 10, 0)
    # The same hours in a UTC space: 07:30 UTC Monday is before opening there.
    assert effective_due(space(tz="UTC"), datetime(2026, 11, 16, 7, 30, tzinfo=dt_timezone.utc)) == \
        datetime(2026, 11, 16, 10, 0, tzinfo=dt_timezone.utc)


def test_dated_closure_exception_rolls_past_it():
    daily = {day: [{"start": "09:00", "end": "17:00"}] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}
    hours = {"weekly": daily, "exceptions": {"2026-11-16": []}}
    assert effective_due(space(hours), ist(2026, 11, 16, 12, 0)) == ist(2026, 11, 17, 10, 0)


def test_grace_is_capped_at_a_session_shorter_than_an_hour():
    short = {"weekly": {"mon": [{"start": "09:00", "end": "09:30"}]}}
    assert effective_due(space(short), ist(2026, 11, 14, 12, 0)) == ist(2026, 11, 16, 9, 30)


def test_no_hours_recorded_is_always_open_and_unchanged():
    due = ist(2026, 11, 14, 3, 0)
    assert effective_due(space({}), due) == due
    assert closed_notice(space({}), due) is None
    assert effective_due(space(), None) is None


def test_a_schedule_that_never_reopens_keeps_the_instant():
    shut = {"weekly": {day: [] for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}}
    due = ist(2026, 11, 16, 12, 0)
    assert effective_due(space(shut), due) == due
    assert closed_notice(space(shut), due) == {"code": "space_closed", "next_open_at": None}


def test_closed_notice_names_the_next_opening():
    notice = closed_notice(space(), ist(2026, 11, 14, 12, 0))
    assert notice == {"code": "space_closed", "next_open_at": "2026-11-16T03:30:00+00:00"}
    assert closed_notice(space(), ist(2026, 11, 16, 12, 0)) is None


@pytest.mark.django_db
def test_renewal_rolls_the_new_due_forward_and_keeps_the_linked_loan_in_step():
    # 2027-01-02 is a Saturday; +7 days lands on Saturday 2027-01-09 -> Monday 09:00 IST + 1h grace.
    makerspace, _, _, _, loan, policy, _ = setup_loan("due-renew", due_at=ist(2027, 1, 2, 12, 0))
    makerspace.timezone, makerspace.opening_hours = "Asia/Kolkata", HOURS
    makerspace.save(update_fields=["timezone", "opening_hours"])
    policy.loan_renewal_days = 7
    policy.save(update_fields=["loan_renewal_days"])
    workflow.renew_loan(make_member("due-renew-sm", makerspace), loan, staff=True)
    loan.refresh_from_db()
    assert loan.return_due_at == ist(2027, 1, 11, 10, 0)
    assert PublicToolLoan.objects.get(request=loan).due_at == loan.return_due_at


@pytest.mark.django_db
def test_renewal_without_hours_is_plain_day_arithmetic():
    makerspace, _, _, _, loan, policy, _ = setup_loan("due-renew-plain", due_at=ist(2027, 1, 2, 12, 0))
    policy.loan_renewal_days = 7
    policy.save(update_fields=["loan_renewal_days"])
    workflow.renew_loan(make_member("due-renew-plain-sm", makerspace), loan, staff=True)
    loan.refresh_from_db()
    assert loan.return_due_at == ist(2027, 1, 9, 12, 0)


@pytest.mark.django_db
def test_staff_entered_due_is_kept_and_the_api_warns():
    makerspace, _, _, _, loan, _, _ = setup_loan("due-staff")
    makerspace.timezone, makerspace.opening_hours = "Asia/Kolkata", HOURS
    makerspace.save(update_fields=["timezone", "opening_hours"])
    client = APIClient()
    client.force_authenticate(make_member("due-staff-sm", makerspace))
    path = f"/api/v1/admin/requests/{loan.pk}/return-due"
    closed = ist(2027, 1, 2, 12, 0)
    response = client.post(path, {"return_due_at": closed.isoformat()}, format="json")
    assert response.status_code == 200
    assert response.data["return_due_notice"] == {"code": "space_closed", "next_open_at": "2027-01-04T03:30:00+00:00"}
    loan.refresh_from_db()
    assert loan.return_due_at == closed
    response = client.post(path, {"return_due_at": ist(2027, 1, 4, 12, 0).isoformat()}, format="json")
    assert response.status_code == 200 and response.data["return_due_notice"] is None


@pytest.mark.django_db
def test_computed_pickup_deadline_rolls_forward_but_the_members_window_is_kept():
    makerspace = setup_loan("due-pickup")[0]
    makerspace.timezone, makerspace.opening_hours = "Asia/Kolkata", HOURS
    makerspace.enabled_features = sorted(set(makerspace.enabled_features) | {"loans.enabled", "loans.pickup_windows"})
    makerspace.save(update_fields=["timezone", "opening_hours", "enabled_features"])
    LoanReservationPolicy.objects.create(makerspace=makerspace, pickup_window_hours=24)
    accepted = ist(2027, 1, 1, 12, 0)  # Friday; +24h is Saturday noon
    request = SimpleNamespace(makerspace=makerspace, pickup_from=None, pickup_until=None)
    # A pickup deadline rolls to the close of the next open session, not its opening instant.
    assert deadline_at_accept(request, now=accepted) == ist(2027, 1, 4, 17, 0)
    own = ist(2027, 1, 2, 12, 0)
    request.pickup_until = own
    assert deadline_at_accept(request, now=accepted) == own
