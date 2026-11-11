from tests.events.website_helpers import remove_page
from tests.events.website_helpers import make_page, make_session
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

import pytest
from django.db import connection, IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage, EventSession
from apps.events.services_clone import duplicate_event
from apps.events.services_website import save_content
from tests.events.website_helpers import website_fixture, session, content

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("wall", [datetime(2026, 11, 1, 1, 30), datetime(2026, 3, 8, 2, 30)])
def test_sql_series_anchor_matches_python_fold_zero_at_overlap_and_gap(wall):
    expected = wall.replace(tzinfo=ZoneInfo("America/New_York"), fold=0)
    with connection.cursor() as cursor:
        cursor.execute("SELECT event_website_wall_start(%s::timestamp, %s)", [wall, "America/New_York"])
        assert cursor.fetchone()[0] == expected.astimezone(dt_timezone.utc)


def attach(event):
    start = event.starts_at
    series = EventSeries.objects.create(makerspace=event.makerspace, title="Series", recurrence_timezone="UTC",
        dtstart_local_date=start.date(), dtstart_local_time=start.timetz().replace(tzinfo=None),
        recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=120, status="published")
    event.series = series; event.series_revision = 1; event.series_occurrence_key = "first"
    event.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    return series


def test_attached_clone_copies_short_override_before_inheriting_long_programme():
    space, actor, event, own, _ = website_fixture()
    series = attach(event)
    event.ends_at = event.starts_at + timedelta(hours=1)
    event.save(update_fields=["ends_at"])
    make_session(page=own, slug="short", title="Short", starts_at=event.starts_at, ends_at=event.ends_at)
    default = make_page(makerspace=space, series=series, released=True)
    make_session(page=default, slug="long", title="Long", starts_at=event.starts_at, ends_at=event.starts_at + timedelta(hours=2))
    clone = duplicate_event(event, actor=actor, attach_series=True)
    assert clone.series_id == series.pk and not clone.website_page.released
    assert clone.website_page.sessions.get().slug == "short"


def test_series_programme_cannot_exceed_short_inheriting_occurrence():
    space, actor, event, own, _ = website_fixture()
    series = attach(event)
    remove_page(own)
    event.ends_at = event.starts_at + timedelta(hours=1)
    event.save(update_fields=["ends_at"])
    page = make_page(makerspace=space, series=series)
    data = {"revision": 1, "sections": [], "sessions": [session(event, ends_at=event.starts_at + timedelta(hours=2))]}
    with pytest.raises(ValidationError): save_content(series, actor=actor, data=data)
    with pytest.raises(IntegrityError), transaction.atomic():
        make_session(page=page, slug="long", title="Long", starts_at=event.starts_at, ends_at=event.starts_at + timedelta(hours=2))


def test_new_occurrence_cannot_inherit_a_programme_outside_its_window():
    space, _, event, _, _ = website_fixture()
    series = attach(event)
    page = make_page(makerspace=space, series=series)
    make_session(page=page, slug="long", title="Long", starts_at=event.starts_at, ends_at=event.ends_at)
    with pytest.raises(IntegrityError), transaction.atomic():
        Event.objects.create(makerspace=space, series=series, series_revision=1, series_occurrence_key="short",
            title="Short", starts_at=event.starts_at + timedelta(days=1), ends_at=event.starts_at + timedelta(days=1, minutes=10))
