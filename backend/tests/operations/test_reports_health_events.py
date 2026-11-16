"""FabLab health counts events and registrations without shadowing the relation."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.events.models import Event, EventRegistration
from apps.operations.reports_health import _event_rows
from tests.events.checkin_helpers import make_event, make_space, register

pytestmark = pytest.mark.django_db


def test_event_section_counts_registrations_and_attendance():
    space = make_space("health-events")
    done = make_event(space, title="Done", status=Event.Status.COMPLETED,
                      starts_at=timezone.now() - timedelta(days=2))
    register(done, status=EventRegistration.Status.ATTENDED, email="a@example.test")
    register(done, status=EventRegistration.Status.REGISTERED, email="b@example.test")
    register(make_event(space, title="Next"), email="c@example.test")
    [row] = _event_rows([space.pk], None)
    assert row["events_in_period"] == 2
    assert row["events_registrations"] == 3
    assert row["events_attended"] == 1
    assert row["events_completed_attendance_rate_percent"] == 50.0
