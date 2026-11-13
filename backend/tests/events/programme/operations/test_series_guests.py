from datetime import time

from django.utils import timezone
import pytest

from apps.events.models import EventRegistration, EventSeries
from apps.events.programme.series_guests import authorized_registrations, project_guests
from apps.events.programme import series_guests
from unittest.mock import Mock
from tests.events.staff_grant_helpers import grant_fixture
from tests.events.ticketing_helpers import account, open_event


@pytest.mark.django_db
def test_series_guest_dedupe_and_per_occurrence_data_permissions():
    space, manager, helper, event, grant = grant_fixture("check_in")
    series = EventSeries.objects.create(makerspace=space, title="Weekly workshops",
        recurrence_timezone="UTC", dtstart_local_date=timezone.now().date(), dtstart_local_time=time(10),
        recurrence_rule="FREQ=WEEKLY;COUNT=2", duration_minutes=120)
    event.series, event.series_revision, event.series_occurrence_key = series, 1, "first"
    event.save(update_fields=["series", "series_revision", "series_occurrence_key"])
    foreign = open_event(space, series=series, series_revision=1, series_occurrence_key="second")
    member = account("series-guest")
    own = EventRegistration.objects.create(event=event, member=member, name="Guest", email=member.email,
                                            phone="123456", status="registered", custom_answers={"secret": "private"})
    EventRegistration.objects.create(event=foreign, member=member, name="Guest", email=member.email,
                                     phone="123456", status="attended")
    rows = authorized_registrations(series, helper, {})
    assert set(rows.values_list("event_id", flat=True)) == {event.pk}
    result = project_guests(rows, [{"member_id": member.pk, "registration_id": None}], actor=helper)
    assert len(result) == 1 and len(result[0]["occurrences"]) == 1
    projected = result[0]["occurrences"][0]
    assert projected["registration_id"] == own.pk
    assert not {"email", "phone", "custom_answers"} & set(projected)
    rows = authorized_registrations(series, manager, {})
    result = project_guests(rows, [{"member_id": member.pk, "registration_id": None}], actor=manager)
    assert len(result) == 1 and len(result[0]["occurrences"]) == 2
    assert all("email" in occurrence for occurrence in result[0]["occurrences"])
    assert authorized_registrations(series, manager, {"status": "registered", "attendance": "attended"}).count() == 0


@pytest.mark.django_db
def test_v2_private_snapshots_require_an_installed_live_answer_projector(monkeypatch):
    _, manager, member, event, _ = grant_fixture()
    snapshot = {"version": 2, "form_id": "example", "form_revision": 1, "answers": [
        {"id": "age", "label": "Age", "type": "age_at_event", "derivation_id": 77}]}
    EventRegistration.objects.create(event=event, member=member, name="Guest", email=member.email,
                                     phone="123456", status="registered", custom_answers=snapshot)
    rows = EventRegistration.objects.filter(event=event)
    identity = [{"member_id": member.pk, "registration_id": None}]
    monkeypatch.setattr(series_guests, "answer_projector", lambda: None)
    data = project_guests(rows, identity, actor=manager)[0]["occurrences"][0]
    assert data["custom_answers"] is None
    assert data["custom_answers_unavailable_reason"] == "v2_projection_unavailable"
    assert "derivation_id" not in str(data)
    projector = Mock(return_value={"answers": [{"id": "age", "value": 25}]})
    monkeypatch.setattr(series_guests, "answer_projector", lambda: projector)
    data = project_guests(rows, identity, actor=manager)[0]["occurrences"][0]
    assert data["custom_answers"] == {"answers": [{"id": "age", "value": 25}]}
    projector.assert_called_once()
