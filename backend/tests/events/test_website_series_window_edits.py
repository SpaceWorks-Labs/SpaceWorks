from tests.events.website_helpers import remove_page
from tests.events.website_helpers import make_page, make_session
"""Series anchor changes must preserve the programme in retained occurrences."""

from datetime import datetime, time, timedelta, timezone as dt_timezone

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.models import AuditLog
from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage, EventSession
from apps.events.services_series_update import update_series
from apps.events.website_projection import project
from tests.events.website_helpers import website_fixture
from tests.events.website_helpers import snapshot

pytestmark = pytest.mark.django_db(transaction=True)


def series_programme(monkeypatch, *, session_end=120, override=False):
    start = datetime(2026, 10, 15, 9, tzinfo=dt_timezone.utc)
    now = start + timedelta(minutes=45)
    monkeypatch.setattr(timezone, "now", lambda: now)
    space, actor, event, own, _ = website_fixture()
    event.starts_at, event.ends_at = start, start + timedelta(hours=2)
    event.save(update_fields=["starts_at", "ends_at"])
    series = EventSeries.objects.create(
        makerspace=space, title="Series", recurrence_timezone="UTC",
        dtstart_local_date=start.date(), dtstart_local_time=time(9),
        recurrence_rule="FREQ=DAILY;COUNT=2", duration_minutes=120,
        registration_audience="accounts", status="published",
    )
    event.series, event.series_revision = series, 1
    event.series_occurrence_key = "1:20261015T090000"
    event.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    if override:
        make_session(
            page=own, slug="local", title="Local", visibility="published",
            starts_at=start, ends_at=start + timedelta(minutes=30),
        )
    else:
        remove_page(own)
    # A longer occurrence must not hide the shorter, retained occurrence's violation.
    Event.objects.create(
        makerspace=space, series=series, series_revision=1,
        series_occurrence_key="1:20261016T090000", title="Long occurrence",
        starts_at=start + timedelta(days=1), ends_at=start + timedelta(days=1, hours=3),
        status="published",
    )
    page = make_page(makerspace=space, series=series, released=True)
    for slug, first, last in [("early", 0, 30), ("late", session_end - 30, session_end)]:
        make_session(
            page=page, slug=slug, title=slug, visibility="published",
            starts_at=start + timedelta(minutes=first), ends_at=start + timedelta(minutes=last),
        )
    return actor, event, series, page, now


def edit_series(writer, series, actor, now, changes):
    if writer == "service":
        update_series(series, actor=actor, effective_from=now, **changes)
    else:
        with transaction.atomic():
            EventSeries.objects.filter(pk=series.pk).update(**changes)
            from apps.events.website_revisions import refresh_owner_anchor
            series.refresh_from_db()
            refresh_owner_anchor(series, actor)


@pytest.mark.parametrize("writer", ["service", "sql"])
@pytest.mark.parametrize("anchor", ["time", "date", "timezone"])
def test_new_anchor_cannot_push_inherited_sessions_past_retained_occurrence(monkeypatch, writer, anchor):
    actor, event, series, page, now = series_programme(monkeypatch)
    if anchor == "time":
        changes = {"dtstart_local_time": time(8), "duration_minutes": 180}
    elif anchor == "date":
        changes = {"dtstart_local_date": series.dtstart_local_date - timedelta(days=1),
                   "duration_minutes": 1560}
    else:
        changes = {"recurrence_timezone": "Etc/GMT-1", "duration_minutes": 180}
    before = project(event, public=True)
    original = {field: getattr(series, field) for field in changes}
    error = ValidationError if writer == "service" else IntegrityError
    with pytest.raises(error, match="inherited website sessions"):
        edit_series(writer, series, actor, now, changes)

    series.refresh_from_db()
    event.refresh_from_db()
    page.refresh_from_db()
    assert {field: getattr(series, field) for field in changes} == original
    assert series.revision == 1 and page.revision == 1 and page.released
    assert series.occurrences.count() == 2
    assert event.starts_at < now < event.ends_at and event.status == "published"
    assert project(event, public=True) == before
    assert not AuditLog.objects.filter(action="event.series_updated").exists()


@pytest.mark.parametrize("writer", ["service", "sql"])
def test_anchor_edit_allows_inherited_session_ending_exactly_at_retained_end(monkeypatch, writer):
    actor, event, series, _, now = series_programme(monkeypatch, session_end=90)
    edit_series(writer, series, actor, now,
                {"dtstart_local_time": time(8, 30), "duration_minutes": 150})
    series.refresh_from_db()
    event.refresh_from_db()
    assert series.dtstart_local_time == time(8, 30)
    assert event.starts_at.hour == 9 and event.ends_at.hour == 11
    rows = project(event, public=True)["sessions"]
    # Publication keeps its original UTC anchor after working-anchor changes.
    assert rows[-1]["ends_at"] == event.starts_at + timedelta(minutes=90)
    assert all(event.starts_at <= row["starts_at"] < row["ends_at"] <= event.ends_at for row in rows)


@pytest.mark.parametrize("writer", ["service", "sql"])
def test_anchor_edit_skips_occurrence_with_its_own_page(monkeypatch, writer):
    actor, event, series, _, now = series_programme(monkeypatch, override=True)
    before = project(event, public=True)
    edit_series(writer, series, actor, now,
                {"dtstart_local_time": time(8), "duration_minutes": 180})
    series.refresh_from_db()
    event.refresh_from_db()
    assert series.dtstart_local_time == time(8)
    assert not before["inherited"] and project(event, public=True) == before


@pytest.mark.parametrize("writer", ["service", "sql"])
def test_anchor_edit_allows_series_without_sessions(monkeypatch, writer):
    actor, event, series, page, now = series_programme(monkeypatch)
    page.sessions.all().delete()
    snapshot(page, released=True)
    edit_series(writer, series, actor, now,
                {"dtstart_local_time": time(8), "duration_minutes": 180})
    series.refresh_from_db()
    event.refresh_from_db()
    assert series.dtstart_local_time == time(8)
    assert project(event, public=True)["sessions"] == []
