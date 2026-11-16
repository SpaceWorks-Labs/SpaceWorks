import pytest

from apps.events.services_event_details import update_event
from tests.events.staff_grant_helpers import grant_fixture


@pytest.mark.django_db
def test_shipped_event_edit_invalidates_programme_expected_version():
    _, manager, _, event, _ = grant_fixture()
    previous = event.version
    updated = update_event(event, actor=manager, title="New title")
    assert updated.version == previous + 1
    assert updated.title == "New title"


@pytest.mark.django_db
def test_event_date_source_change_invalidates_prepared_answer_revision():
    from datetime import timedelta
    _, manager, _, event, _ = grant_fixture()
    revision = event.event_date_revision
    updated = update_event(event, actor=manager, starts_at=event.starts_at + timedelta(minutes=5))
    assert updated.event_date_revision == revision + 1
