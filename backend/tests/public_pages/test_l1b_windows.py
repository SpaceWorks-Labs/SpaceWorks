from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo
import pytest
from django.db import connection, IntegrityError, transaction
from django.core.exceptions import ValidationError as ModelValidationError
from apps.events.models import Event, EventSeries
from apps.events.models_website import EventPage
from apps.events.services_website import save_content, set_release
from apps.events.website_projection import project, window
from apps.events.website_revisions import refresh_owner_anchor
from apps.events.website_validation import validate_owner_window
from tests.events.website_helpers import session

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("wall", [datetime(2027, 3, 14, 2, 30), datetime(2027, 11, 7, 1, 30)])
def test_released_inheritance_uses_frozen_dst_anchor_after_live_series_change(event_owner, wall):
    space, actor, _ = event_owner
    series = EventSeries.objects.create(makerspace=space, title="DST programme", recurrence_timezone="America/New_York",
        dtstart_local_date=wall.date(), dtstart_local_time=wall.time(), recurrence_rule="FREQ=DAILY;COUNT=2",
        duration_minutes=120, status="published")
    start, end = window(series)
    assert start == wall.replace(tzinfo=ZoneInfo("America/New_York"), fold=0).astimezone(dt_timezone.utc)
    with connection.cursor() as cursor:
        cursor.execute("SELECT event_website_wall_start(%s::timestamp, %s)", [wall, series.recurrence_timezone])
        assert cursor.fetchone()[0] == start
    occurrence = Event.objects.create(makerspace=space, series=series, series_revision=1,
        series_occurrence_key="dst", title="DST occurrence", status="published", is_public=True,
        starts_at=start + timedelta(days=2), ends_at=end + timedelta(days=2))
    save_content(series, actor=actor, data={"revision": 0, "sections": [], "sessions": [{
        "slug": "talk", "title": "Talk", "body": "", "track": None, "room": None, "speakers": [],
        "visibility": "published", "starts_at": start + timedelta(minutes=30), "ends_at": start + timedelta(minutes=60)}]})
    page = EventPage.objects.get(series=series)
    set_release(series, actor=actor, released=True, revision=page.revision)
    before = project(occurrence, public=True)["sessions"]
    # Enlarge the live window without changing the retained publication anchor.
    earlier = wall - timedelta(minutes=30)
    with transaction.atomic():
        EventSeries.objects.filter(pk=series.pk).update(dtstart_local_time=earlier.time(), duration_minutes=180)
        series.refresh_from_db()
        refresh_owner_anchor(series, actor)
    page.refresh_from_db()
    assert page.published_revision.source_anchor_start == start
    assert page.draft_revision.source_anchor_start == window(series)[0]
    assert project(occurrence, public=True)["sessions"] == before


def test_removed_late_draft_does_not_permit_shortening_retained_public_window(event_owner):
    _, actor, event = event_owner
    save_content(event, actor=actor, data={"revision": 0, "sections": [],
        "sessions": [session(event, starts_at=event.ends_at - timedelta(minutes=30), ends_at=event.ends_at)]})
    set_release(event, actor=actor, released=True, revision=project(event)["revision"])
    data = project(event)
    data["sessions"] = []
    save_content(event, actor=actor, data=data)
    shorter = event.starts_at + timedelta(minutes=30)
    event.ends_at = shorter
    with pytest.raises(ModelValidationError):
        validate_owner_window(event)
    with pytest.raises(IntegrityError), transaction.atomic():
        Event.objects.filter(pk=event.pk).update(ends_at=shorter)
    event.refresh_from_db()
    page = EventPage.objects.get(event=event)
    with transaction.atomic():
        EventPage.objects.filter(pk=page.pk).update(released=False)
        Event.objects.filter(pk=event.pk).update(ends_at=shorter)
    assert project(event, public=False)["sessions"] == []


@pytest.mark.parametrize("first", ["publication", "occurrence"])
def test_raw_publication_and_short_occurrence_insert_cannot_both_commit(event_owner, first):
    from contextlib import ExitStack
    from tests.public_pages.l1b_threads import database_worker, wait_for_blocked
    space, actor, base = event_owner
    start = base.starts_at
    series = EventSeries.objects.create(makerspace=space, title="Concurrent programme", recurrence_timezone="UTC",
        dtstart_local_date=start.date(), dtstart_local_time=start.time(), recurrence_rule="FREQ=DAILY;COUNT=2",
        duration_minutes=120, status="published")
    save_content(series, actor=actor, data={"revision": 0, "sections": [], "sessions": [session(base, ends_at=base.ends_at)]})
    page = EventPage.objects.get(series=series)
    retained = page.draft_revision_id
    data = project(series)
    data["sessions"] = []
    save_content(series, actor=actor, data=data)
    def publish():
        with transaction.atomic():
            EventPage.objects.filter(pk=page.pk).update(released=True, published_revision_id=retained)
    def insert():
        return Event.objects.create(makerspace=space, series=series, series_revision=1,
            series_occurrence_key="concurrent-short", title="Short occurrence", status="published",
            starts_at=start + timedelta(days=1), ends_at=start + timedelta(days=1, minutes=10))
    with ExitStack() as stack:
        with transaction.atomic():
            if first == "publication":
                EventSeries.objects.select_for_update().get(pk=series.pk)
                publish()
                worker = insert
            else:
                insert()
                worker = publish
            future, pid = stack.enter_context(database_worker(worker))
            wait_for_blocked(pid)
        with pytest.raises(IntegrityError):
            future.result(timeout=15)
    page.refresh_from_db()
    short_exists = Event.objects.filter(series=series, series_occurrence_key="concurrent-short").exists()
    assert page.released is (first == "publication")
    assert short_exists is (first == "occurrence")
