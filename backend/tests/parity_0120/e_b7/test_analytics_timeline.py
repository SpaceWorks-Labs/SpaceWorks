"""E-B7 analytics: adaptive arrival windows, sign-ups per day, written-answer counts."""
from datetime import datetime, timedelta, timezone as utc
from zoneinfo import ZoneInfo

import pytest

from apps.events.programme.analytics_timeline import (
    WINDOW_CHOICES, arrival_windows, bucket_start, signups_by_day, window_minutes_for, written_answer_counts,
)
from tests.events.collab_helpers import make_event, make_member, make_space


@pytest.mark.parametrize("span,window", [(0, 15), (720, 15), (721, 30), (24 * 60, 30),
                                         (3 * 24 * 60, 120), (30 * 24 * 60, 480)])
def test_window_sizing(span, window):
    assert window_minutes_for(span) == window


def test_windows_stay_between_fifteen_minutes_and_eight_hours():
    assert window_minutes_for(10 ** 7) == WINDOW_CHOICES[-1] == 480
    assert window_minutes_for(1) == WINDOW_CHOICES[0] == 15


def test_bucket_start_floors_from_local_midnight():
    local = datetime(2026, 11, 1, 10, 47, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert bucket_start(local, 15).minute == 45
    assert (bucket_start(local, 60).hour, bucket_start(local, 60).minute) == (10, 0)
    assert bucket_start(local, 480).hour == 8


def test_arrival_windows_use_the_event_timezone_and_widen_for_long_spans():
    zone = ZoneInfo("Asia/Kolkata")
    base = datetime(2026, 11, 1, 3, 40, tzinfo=utc.utc)  # 09:10 local
    timeline, window = arrival_windows([base, base + timedelta(minutes=2), base + timedelta(minutes=20)], zone)
    assert window == 15 and [row["count"] for row in timeline] == [2, 1]
    assert (timeline[0]["window_start"].hour, timeline[0]["window_start"].minute) == (9, 0)
    _, wide = arrival_windows([base, base + timedelta(days=5)], zone)
    assert wide > 15
    assert arrival_windows([], zone) == ([], 15)


@pytest.mark.django_db
def test_signups_by_day_counts_registrations():
    from apps.events.models import EventRegistration
    space = make_space("signups-a")
    event = make_event(space)
    for index in range(3):
        person = make_member(space, f"s{index}")
        EventRegistration.objects.create(event=event, member=person, name=person.username, email=person.email,
                                         status="registered")
    rows = signups_by_day(event)
    assert sum(row["count"] for row in rows) == 3 and all("day" in row for row in rows)


@pytest.mark.django_db
def test_written_answer_counts_empty_without_a_survey():
    assert written_answer_counts(make_event(make_space("written-a"))) == []
